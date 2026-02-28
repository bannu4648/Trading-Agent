import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import logging
import json
import os
from datetime import datetime
from run_analysis import run_full_analysis

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

# Initialize the Dash app with a dark theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG, dbc.icons.BOOTSTRAP],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

app.title = "Trading-Agent | Unified Analysis"

# --- Layout Components ---

header = dbc.NavbarSimple(
    brand="TRADING-AGENT UNIFIED DASHBOARD",
    brand_href="#",
    color="primary",
    dark=True,
    class_name="mb-4",
)

input_card = dbc.Card(
    dbc.CardBody([
        html.H5("Stock Analysis", className="card-title"),
        dbc.Input(id="ticker-input", placeholder="Enter Ticker (e.g. AAPL, META)", type="text", className="mb-3"),
        dbc.Button("Run Full Analysis", id="analyze-btn", color="success", className="w-100"),
        html.Div(id="status-output", className="mt-3 text-info small"),
    ]),
    className="mb-4",
)

# Placeholders for results
content_area = html.Div(id="results-content")


app.layout = dbc.Container([
    header,
    dbc.Row([
        dbc.Col(input_card, md=3),
        dbc.Col(content_area, md=9),
    ]),
    dcc.Loading(
        id="loading-spinner",
        type="default",
        children=html.Div(id="loading-trigger"),
        fullscreen=True,
        style={"backgroundColor": "rgba(0,0,0,0.5)"}
    )
], fluid=True)

# --- Callbacks ---

@app.callback(
    Output("results-content", "children"),
    Output("status-output", "children"),
    Input("analyze-btn", "n_clicks"),
    State("ticker-input", "value"),
    prevent_initial_call=True,
)
def run_analysis_ui(n_clicks, ticker_text):
    if not ticker_text:
        return dash.no_update, "Please enter a ticker symbol."
    
    tickers = [t.strip().upper() for t in ticker_text.split(",") if t.strip()]
    if not tickers:
        return dash.no_update, "Invalid ticker format."

    start_time = datetime.now()
    try:
        # This calls the unified orchestrator we built
        results = run_full_analysis(tickers=tickers)
        duration = (datetime.now() - start_time).total_seconds()
        
        # Trader Agent output (shared across all tickers)
        trader_data = results.get("trader", {})
        trader_orders = trader_data.get("orders", [])
        trader_method = trader_data.get("sizing_method_chosen", "N/A")
        trader_rationale = trader_data.get("overall_rationale", "")
        trader_error = trader_data.get("error")

        # Build the UI display for each ticker
        ticker_tabs = []
        for ticker in tickers:
            data = results["results"].get(ticker, {})
            tech = data.get("technical", {})
            sent = data.get("sentiment", {})
            synth = data.get("synthesis", "No synthesis available.")

            # Summary Card (Synthesis)
            summary_card = dbc.Card([
                dbc.CardHeader(html.H4(f"Strategy: {ticker}", className="mb-0")),
                dbc.CardBody(dcc.Markdown(synth)),
            ], color="dark", outline=True, className="mb-4 shadow")

            # Technical Details
            tech_signals = tech.get("signals", [])
            tech_rows = [
                html.Tr([html.Td(s.get("name")), html.Td(s.get("direction").upper()), html.Td(f"{s.get('strength', 0):.2f}")]) 
                for s in tech_signals
            ]
            
            tech_panel = dbc.Card([
                dbc.CardHeader(html.H5("Technical Indicators", className="mb-0")),
                dbc.CardBody([
                    html.Table([
                        html.Thead(html.Tr([html.Th("Signal"), html.Th("Direction"), html.Th("Strength")])),
                        html.Tbody(tech_rows)
                    ], className="table table-dark table-hover small"),
                    html.P(f"Summary: {tech.get('summary')}", className="mt-2 text-muted italic")
                ])
            ], color="secondary", outline=True)

            # Sentiment Details
            sent_label = sent.get("sentiment_label", "NEUTRAL")
            label_color = "success" if sent_label == "POSITIVE" else "danger" if sent_label == "NEGATIVE" else "warning"
            
            sent_panel = dbc.Card([
                dbc.CardHeader(html.H5("Market Sentiment", className="mb-0")),
                dbc.CardBody([
                    html.Div([
                        html.Span(f"{sent_label}", className=f"badge bg-{label_color} fs-4 me-2"),
                        html.Span(f"Score: {sent.get('sentiment_score', 0):.3f}", className="text-info me-2"),
                        html.Span(f"Conf: {sent.get('confidence', 0):.2%}", className="text-muted"),
                    ], className="mb-3"),
                    html.H6("Bull vs Bear Consensus"),
                    html.P(sent.get("debate", {}).get("resolution"), className="small")
                ])
            ], color="secondary", outline=True)

            # Trader Agent — Trade Order for this ticker (embedded per-ticker in results)
            order = data.get("trade_order")

            if trader_error:
                trader_body = html.P(f"Error: {trader_error}", className="text-danger small")
            elif order:
                action = order.get("action", "N/A")
                action_color = "success" if action == "BUY" else "danger" if action == "SELL" else "warning"
                proposed_w = order.get("proposed_weight", 0)
                delta_w = order.get("weight_delta", 0)
                delta_color = "text-success" if delta_w >= 0 else "text-danger"
                trader_body = html.Div([
                    html.Div([
                        html.Span(action, className=f"badge bg-{action_color} fs-5 me-3"),
                        html.Span(f"Target weight: {proposed_w:.1%}", className="text-info me-3"),
                        html.Span(
                            f"Delta: {delta_w:+.1%}",
                            className=f"{delta_color} me-3"
                        ),
                        html.Span(
                            f"Method: {order.get('sizing_method_used', 'N/A')}",
                            className="text-muted small"
                        ),
                    ], className="mb-2"),
                    html.P(order.get("rationale", ""), className="small text-muted fst-italic"),
                ])
            else:
                trader_body = html.P("No trade order generated for this ticker.", className="text-muted small")

            trader_panel = dbc.Card([
                dbc.CardHeader(html.Div([
                    html.H5("Trader Agent", className="mb-0 d-inline me-3"),
                    html.Span(
                        f"Sizing: {trader_method}",
                        className="badge bg-primary small"
                    ),
                ])),
                dbc.CardBody([
                    trader_body,
                    html.Hr(className="my-2"),
                    html.P(trader_rationale, className="small text-muted") if trader_rationale else None,
                ])
            ], color="primary", outline=True)

            ticker_tabs.append(dbc.Tab(label=ticker, children=[
                html.Div([
                    summary_card,
                    dbc.Row([
                        dbc.Col(tech_panel, md=6),
                        dbc.Col(sent_panel, md=6),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Col(trader_panel, md=12),
                    ])
                ], className="mt-3")
            ]))

        status_msg = f"Done in {duration:.1f}s. Report saved to ./results/"
        return dbc.Tabs(ticker_tabs), status_msg

    except Exception as e:
        logger.exception("Analysis Error")
        return html.Pre(f"Error: {str(e)}", className="text-danger"), f"Failed: {str(e)}"

if __name__ == "__main__":
    # Get port from env or default to 8050
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=True, host="0.0.0.0", port=port)

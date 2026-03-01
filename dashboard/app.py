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

            # Fundamentals Details
            fund = data.get("fundamentals", {})
            fund_display_keys = [
                "Company Name", "Sector", "Share Price", "Market Cap",
                "P/E Ratio", "Forward P/E", "PEG Ratio",
                "Profit Margin", "Operating Margin", "ROE", "ROA",
                "Current Ratio", "Debt/Equity",
                "Revenue Growth", "Earnings Growth",
                "Piotroski F-Score",   # Change 2
            ]
            fund_rows = [
                html.Tr([html.Td(k), html.Td(str(fund.get(k, "N/A")))])
                for k in fund_display_keys
            ]
            # Colour the Piotroski row
            fscore_str = str(fund.get("Piotroski F-Score", ""))
            fscore_color = (
                "text-success" if "Strong" in fscore_str
                else "text-danger" if "Weak" in fscore_str
                else "text-warning"
            )
            fund_panel = dbc.Card([
                dbc.CardHeader(html.H5("Fundamentals", className="mb-0")),
                dbc.CardBody([
                    html.Table([
                        html.Thead(html.Tr([html.Th("Metric"), html.Th("Value")])),
                        html.Tbody(fund_rows)
                    ], className="table table-dark table-hover small"),
                    html.P(
                        f"📊 Piotroski F-Score: {fscore_str}",
                        className=f"fw-bold {fscore_color} mt-2 small"
                    ) if fscore_str and fscore_str != "N/A" else None,
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
                        dbc.Col(tech_panel, md=4),
                        dbc.Col(sent_panel, md=4),
                        dbc.Col(fund_panel, md=4),
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Col(trader_panel, md=12),
                    ])
                ], className="mt-3")
            ]))

        # ── Portfolio Allocation Summary (across all tickers) ──
        allocation_rows = []
        alloc_tickers = []
        alloc_weights = []
        alloc_colors = []
        total_invested = 0.0

        for ticker in tickers:
            order = results["results"].get(ticker, {}).get("trade_order", {})
            action = order.get("action", "HOLD")
            weight = order.get("proposed_weight", 0) or 0
            method = order.get("sizing_method_used", "N/A")
            rationale = order.get("rationale", "")
            total_invested += weight

            action_color = "success" if action == "BUY" else "danger" if action == "SELL" else "warning"
            alloc_tickers.append(ticker)
            alloc_weights.append(weight)
            alloc_colors.append("#28a745" if action == "BUY" else "#dc3545" if action == "SELL" else "#ffc107")

            allocation_rows.append(html.Tr([
                html.Td(ticker, className="fw-bold"),
                html.Td(html.Span(action, className=f"badge bg-{action_color}")),
                html.Td(f"{weight:.1%}"),
                html.Td(method),
                html.Td(rationale[:80] + "..." if len(rationale) > 80 else rationale, className="small"),
            ]))

        cash_pct = 1.0 - total_invested
        alloc_tickers.append("CASH")
        alloc_weights.append(cash_pct)
        alloc_colors.append("#6c757d")

        # Build horizontal bar chart using Plotly
        import plotly.graph_objects as go
        alloc_fig = go.Figure()
        alloc_fig.add_trace(go.Bar(
            y=alloc_tickers,
            x=[w * 100 for w in alloc_weights],
            orientation="h",
            marker_color=alloc_colors,
            text=[f"{w:.1%}" for w in alloc_weights],
            textposition="auto",
        ))
        alloc_fig.update_layout(
            title=None,
            xaxis_title="Allocation (%)",
            yaxis_title=None,
            template="plotly_dark",
            height=max(200, len(alloc_tickers) * 60),
            margin=dict(l=80, r=20, t=10, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        portfolio_summary_panel = dbc.Card([
            dbc.CardHeader(html.Div([
                html.H5("💼 Portfolio Allocation", className="mb-0 d-inline me-3"),
                html.Span(
                    f"Method: {trader_method}" if trader_method and trader_method != "N/A" else "Method: Formula Fallback",
                    className="badge bg-info me-2"
                ),
                html.Span(f"Invested: {total_invested:.1%}", className="badge bg-primary me-2"),
                html.Span(f"Cash: {cash_pct:.1%}", className="badge bg-secondary"),
            ])),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dcc.Graph(figure=alloc_fig, config={"displayModeBar": False}),
                    ], md=5),
                    dbc.Col([
                        html.Table([
                            html.Thead(html.Tr([
                                html.Th("Ticker"), html.Th("Action"), html.Th("Weight"),
                                html.Th("Method"), html.Th("Rationale"),
                            ])),
                            html.Tbody(allocation_rows)
                        ], className="table table-dark table-hover small"),
                    ], md=7),
                ]),
                html.Hr(className="my-2"),
                html.P(
                    trader_rationale if trader_rationale else "Sizing determined by formula fallback (LLM unavailable).",
                    className="small text-muted fst-italic"
                ),
            ])
        ], color="info", outline=True, className="mt-4 shadow")

        # ── Portfolio Validation ──
        risk = results.get("risk_report", {})
        risk_level = risk.get("risk_level", "UNKNOWN")
        risk_color = "success" if risk_level == "LOW" else "warning" if risk_level == "MEDIUM" else "danger"
        risk_warnings = risk.get("warnings", [])
        risk_metrics = risk.get("metrics", {})
        risk_panel = dbc.Card([
            dbc.CardHeader(html.Div([
                html.H5("📋 Portfolio Validation", className="mb-0 d-inline me-3"),
                html.Span(risk_level, className=f"badge bg-{risk_color} ms-2"),
            ])),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.P(f"💰 Total Invested: {risk_metrics.get('total_invested', 0):.1%}", className="mb-1"),
                        html.P(f"💵 Cash Buffer: {risk_metrics.get('cash_buffer', 0):.1%}", className="mb-1 text-success"),
                        html.P(f"📈 Portfolio Vol: {risk_metrics.get('weighted_portfolio_volatility', 0):.1%}", className="mb-1"),
                        html.P(f"🎯 Positions: {risk_metrics.get('num_positions', 0)}", className="mb-1"),
                    ], md=4),
                    dbc.Col([
                        html.H6("⚠️ Warnings:" if risk_warnings else "✅ No warnings", className="text-warning" if risk_warnings else "text-success"),
                        html.Ul([html.Li(w, className="small text-muted") for w in risk_warnings])
                    ], md=8),
                ])
            ])
        ], color=risk_color, outline=True, className="mt-3")

        status_msg = f"Done in {duration:.1f}s. Report saved to ./results/"
        return html.Div([
            portfolio_summary_panel,
            html.Hr(className="my-4"),
            dbc.Tabs(ticker_tabs),
            risk_panel
        ]), status_msg

    except Exception as e:
        logger.exception("Analysis Error")
        return html.Pre(f"Error: {str(e)}", className="text-danger"), f"Failed: {str(e)}"

if __name__ == "__main__":
    # Get port from env or default to 8050
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=True, host="0.0.0.0", port=port)

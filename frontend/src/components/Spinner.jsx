export default function Spinner({ text = 'Loading...' }) {
    return (
        <div className="spinner-overlay">
            <div className="spinner" />
            <p className="spinner-text">{text}</p>
        </div>
    );
}

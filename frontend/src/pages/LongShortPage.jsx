import { Navigate } from 'react-router-dom';

/** Backward compatibility: old sidebar linked here. */
export default function LongShortPage() {
    return <Navigate to="/?mode=top20" replace />;
}

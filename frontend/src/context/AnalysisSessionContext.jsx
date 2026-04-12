import { createContext, useCallback, useContext, useMemo, useState } from 'react';

const AnalysisSessionContext = createContext(null);

/**
 * Keeps the last pipeline run + form state in memory while navigating between
 * sidebar routes. Clears on full browser refresh (new load). Not sessionStorage
 * so very large JSON is not duplicated and quota is avoided.
 */
export function AnalysisSessionProvider({ children }) {
    const [session, setSession] = useState(null);

    const mergeSession = useCallback((patch) => {
        setSession((prev) => ({ ...(prev || {}), ...patch }));
    }, []);

    const clearSession = useCallback(() => {
        setSession(null);
    }, []);

    const value = useMemo(
        () => ({ session, mergeSession, clearSession }),
        [session, mergeSession, clearSession],
    );

    return <AnalysisSessionContext.Provider value={value}>{children}</AnalysisSessionContext.Provider>;
}

export function useAnalysisSession() {
    const ctx = useContext(AnalysisSessionContext);
    if (!ctx) {
        throw new Error('useAnalysisSession must be used within AnalysisSessionProvider');
    }
    return ctx;
}

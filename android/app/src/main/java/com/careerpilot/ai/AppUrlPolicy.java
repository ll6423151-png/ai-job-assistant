package com.careerpilot.ai;

import java.net.URI;
import java.net.URISyntaxException;

final class AppUrlPolicy {
    private final URI appOrigin;
    private final boolean debug;

    AppUrlPolicy(String baseUrl, boolean debug) {
        this.debug = debug;
        URI parsed;
        try {
            parsed = new URI(baseUrl);
        } catch (URISyntaxException exception) {
            parsed = null;
        }
        appOrigin = parsed;
    }

    boolean isConfigured() {
        if (appOrigin == null || appOrigin.getHost() == null || appOrigin.getHost().trim().isEmpty()) return false;
        boolean validScheme = "https".equalsIgnoreCase(appOrigin.getScheme())
                || (debug && "http".equalsIgnoreCase(appOrigin.getScheme()));
        return validScheme && !appOrigin.getHost().endsWith(".invalid");
    }

    boolean isAppUrl(String value) {
        if (appOrigin == null || value == null) return false;
        try {
            URI candidate = new URI(value);
            if (candidate.getHost() == null) return false;
            return appOrigin.getScheme().equalsIgnoreCase(candidate.getScheme())
                    && appOrigin.getHost().equalsIgnoreCase(candidate.getHost())
                    && effectivePort(appOrigin) == effectivePort(candidate);
        } catch (URISyntaxException exception) {
            return false;
        }
    }

    private int effectivePort(URI value) {
        if (value.getPort() != -1) return value.getPort();
        return "https".equalsIgnoreCase(value.getScheme()) ? 443 : 80;
    }
}

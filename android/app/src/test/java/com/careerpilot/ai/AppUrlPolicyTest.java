package com.careerpilot.ai;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class AppUrlPolicyTest {
    @Test
    public void releaseRequiresConfiguredHttpsOrigin() {
        assertTrue(new AppUrlPolicy("https://app.example.com", false).isConfigured());
        assertFalse(new AppUrlPolicy("http://app.example.com", false).isConfigured());
        assertFalse(new AppUrlPolicy("https://app.careerpilot.invalid", false).isConfigured());
    }

    @Test
    public void debugAllowsLocalHttpOrigin() {
        assertTrue(new AppUrlPolicy("http://10.0.2.2:3003", true).isConfigured());
    }

    @Test
    public void navigationOnlyKeepsSameOriginInsideApp() {
        AppUrlPolicy policy = new AppUrlPolicy("https://app.example.com", false);
        assertTrue(policy.isAppUrl("https://app.example.com/login"));
        assertTrue(policy.isAppUrl("https://app.example.com:443/api/auth/me"));
        assertFalse(policy.isAppUrl("https://www.zhaopin.com/jobdetail/1"));
        assertFalse(policy.isAppUrl("http://app.example.com/login"));
        assertFalse(policy.isAppUrl("https://app.example.com:8443/login"));
    }
}

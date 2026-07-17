package com.careerpilot.ai;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class ZhaopinLaunchTargetTest {
    @Test
    public void usesTheZhaopinConsumerAppAndOfficialFallbacks() {
        assertEquals("com.zhaopin.social", ZhaopinLaunchTarget.PACKAGE_NAME);
        assertEquals("market://details?id=com.zhaopin.social", ZhaopinLaunchTarget.STORE_URL);
        assertEquals("https://www.zhaopin.com/mobile", ZhaopinLaunchTarget.OFFICIAL_URL);
    }
}

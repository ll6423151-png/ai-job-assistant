import assert from "node:assert/strict";
import test from "node:test";

import { NextRequest } from "next/server.js";

import { middleware } from "../src/middleware.ts";

test("public redirects discard the private Next.js port", () => {
  const request = new NextRequest("http://127.0.0.1:3000/", {
    headers: {
      host: "127.0.0.1:3000",
      "x-forwarded-host": "careerpilot.example.com",
      "x-forwarded-proto": "https",
    },
  });

  const response = middleware(request);

  assert.equal(response.headers.get("location"), "https://careerpilot.example.com/welcome");
});

test("Cloudflare HTTPS redirects discard a forwarded private port", () => {
  const request = new NextRequest("http://127.0.0.1:3000/", {
    headers: {
      "x-forwarded-host": "careerpilot.example.com:3000",
      "x-forwarded-proto": "https",
    },
  });

  const response = middleware(request);

  assert.equal(response.headers.get("location"), "https://careerpilot.example.com/welcome");
});

test("forwarded public ports remain explicit when provided", () => {
  const request = new NextRequest("http://127.0.0.1:3000/", {
    headers: {
      "x-forwarded-host": "careerpilot.example.com:8443",
      "x-forwarded-proto": "https",
    },
  });

  const response = middleware(request);

  assert.equal(response.headers.get("location"), "https://careerpilot.example.com:8443/welcome");
});

test("a stale session cookie cannot redirect the login page back to the workspace", () => {
  const request = new NextRequest("https://careerpilot.example.com/login", {
    headers: {
      cookie: "careerpilot_session=expired-session",
    },
  });

  const response = middleware(request);

  assert.equal(response.headers.get("location"), null);
  assert.equal(response.headers.get("x-middleware-next"), "1");
});

import { beforeEach, describe, expect, it } from "vitest";
import { captureWidgetAccessToken, getWidgetAccessToken } from "../api/access-token";

function setUrl(url: string) {
  window.history.replaceState(null, "", url);
}

beforeEach(() => {
  window.sessionStorage.clear();
  setUrl("http://localhost/");
});

describe("captureWidgetAccessToken / getWidgetAccessToken", () => {
  it("returns null when neither the URL nor storage has a token", () => {
    captureWidgetAccessToken();
    expect(getWidgetAccessToken()).toBeNull();
  });

  it("captures a token from the URL, persists it, and strips it from the visible URL", () => {
    setUrl("http://localhost/?access_token=invite-abc123");

    captureWidgetAccessToken();

    expect(getWidgetAccessToken()).toBe("invite-abc123");
    expect(window.sessionStorage.getItem("obi_widget_access_token")).toBe("invite-abc123");
    expect(window.location.search).not.toContain("access_token");
  });

  it("preserves other query params while stripping only access_token", () => {
    setUrl("http://localhost/?foo=bar&access_token=invite-abc123&baz=qux");

    captureWidgetAccessToken();

    expect(window.location.search).not.toContain("access_token");
    expect(window.location.search).toContain("foo=bar");
    expect(window.location.search).toContain("baz=qux");
  });

  it("reuses a previously captured token when the URL has no param on a later call", () => {
    setUrl("http://localhost/?access_token=invite-abc123");
    captureWidgetAccessToken();

    setUrl("http://localhost/");
    captureWidgetAccessToken();

    expect(getWidgetAccessToken()).toBe("invite-abc123");
  });

  it("overwrites a stored token when a new one is present in the URL", () => {
    setUrl("http://localhost/?access_token=old-token");
    captureWidgetAccessToken();

    setUrl("http://localhost/?access_token=new-token");
    captureWidgetAccessToken();

    expect(getWidgetAccessToken()).toBe("new-token");
  });
});

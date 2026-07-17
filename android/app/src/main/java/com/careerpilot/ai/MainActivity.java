package com.careerpilot.ai;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.JavascriptInterface;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.util.Locale;

public class MainActivity extends Activity {
    private static final String TAG = "CareerPilot";
    private static final int FILE_CHOOSER_REQUEST = 1201;
    private static final int MICROPHONE_PERMISSION_REQUEST = 1202;

    private WebView webView;
    private ProgressBar progressBar;
    private LinearLayout errorView;
    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest pendingWebPermission;
    private AppUrlPolicy urlPolicy;
    private TextToSpeech textToSpeech;
    private boolean textToSpeechReady;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        setTheme(R.style.Theme_CareerPilot);
        super.onCreate(savedInstanceState);
        configureSystemBars();
        urlPolicy = new AppUrlPolicy(BuildConfig.APP_BASE_URL, BuildConfig.DEBUG);
        buildInterface();
        configureWebView();
        configureNativeSpeech();
        if (savedInstanceState == null) {
            if (isConfiguredBaseUrl()) {
                webView.loadUrl(BuildConfig.APP_BASE_URL + "/");
            } else {
                showConfigurationError();
            }
        } else {
            webView.restoreState(savedInstanceState);
        }
    }

    private void configureSystemBars() {
        boolean dark = (getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)
                == Configuration.UI_MODE_NIGHT_YES;
        getWindow().setStatusBarColor(getColor(dark ? R.color.surface_dark : R.color.surface_light));
        getWindow().setNavigationBarColor(getColor(dark ? R.color.surface_dark : R.color.surface_light));
        getWindow().getDecorView().setSystemUiVisibility(dark ? 0 : View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
    }

    private void buildInterface() {
        FrameLayout root = new FrameLayout(this);
        webView = new WebView(this);
        root.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        ));

        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        FrameLayout.LayoutParams progressParams = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                dp(3)
        );
        progressParams.gravity = Gravity.TOP;
        root.addView(progressBar, progressParams);

        errorView = new LinearLayout(this);
        errorView.setOrientation(LinearLayout.VERTICAL);
        errorView.setGravity(Gravity.CENTER);
        errorView.setPadding(dp(28), dp(28), dp(28), dp(28));
        errorView.setVisibility(View.GONE);

        TextView title = new TextView(this);
        title.setText(R.string.connection_error_title);
        title.setTextSize(20);
        title.setGravity(Gravity.CENTER);
        errorView.addView(title);

        TextView message = new TextView(this);
        message.setText(R.string.connection_error_message);
        message.setTextSize(14);
        message.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams messageParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        messageParams.setMargins(0, dp(12), 0, dp(20));
        errorView.addView(message, messageParams);

        Button retry = new Button(this);
        retry.setText(R.string.retry);
        retry.setOnClickListener(view -> {
            errorView.setVisibility(View.GONE);
            webView.setVisibility(View.VISIBLE);
            webView.reload();
        });
        errorView.addView(retry);

        root.addView(errorView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        ));
        setContentView(root);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setUserAgentString(settings.getUserAgentString() + " CareerPilotAndroid/1.0");

        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, false);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        webView.addJavascriptInterface(new NativeSpeechInterface(), "CareerPilotNativeSpeech");
        webView.addJavascriptInterface(new NativeAppsInterface(), "CareerPilotNativeApps");

        webView.setWebViewClient(new CareerPilotWebViewClient());
        webView.setWebChromeClient(new CareerPilotWebChromeClient());
        webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> openExternal(url));
    }

    private boolean isConfiguredBaseUrl() {
        return urlPolicy.isConfigured();
    }

    private boolean isAppUrl(Uri uri) {
        return uri != null && urlPolicy.isAppUrl(uri.toString());
    }

    private void showConfigurationError() {
        webView.setVisibility(View.GONE);
        errorView.setVisibility(View.VISIBLE);
        Toast.makeText(this, R.string.server_not_configured, Toast.LENGTH_LONG).show();
    }

    private void showNetworkError() {
        webView.setVisibility(View.GONE);
        errorView.setVisibility(View.VISIBLE);
    }

    private void openExternal(String value) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(value)));
        } catch (ActivityNotFoundException exception) {
            Toast.makeText(this, R.string.no_browser, Toast.LENGTH_SHORT).show();
        }
    }

    private String openZhaopin() {
        try {
            Intent launchIntent = getPackageManager().getLaunchIntentForPackage(ZhaopinLaunchTarget.PACKAGE_NAME);
            if (launchIntent != null) {
                Log.i(TAG, "Opening installed Zhaopin app");
                startActivity(launchIntent);
                return "app_opened";
            }
            Intent appUrlIntent = new Intent(Intent.ACTION_VIEW, Uri.parse(ZhaopinLaunchTarget.OFFICIAL_URL));
            appUrlIntent.setPackage(ZhaopinLaunchTarget.PACKAGE_NAME);
            if (appUrlIntent.resolveActivity(getPackageManager()) != null) {
                Log.i(TAG, "Opening Zhaopin installed app through deep link");
                startActivity(appUrlIntent);
                return "app_opened";
            }
            Log.i(TAG, "Zhaopin app is not installed; opening app store");
            if (tryOpenExternal(ZhaopinLaunchTarget.STORE_URL)) return "store_opened";
            Log.i(TAG, "No app store available; opening official Zhaopin website");
            if (tryOpenExternal(ZhaopinLaunchTarget.OFFICIAL_URL)) return "website_opened";
        } catch (RuntimeException exception) {
            Log.e(TAG, "Unable to open Zhaopin", exception);
        }
        runOnUiThread(() -> Toast.makeText(this, R.string.zhaopin_open_failed, Toast.LENGTH_SHORT).show());
        return "failed";
    }

    private String openZhaopinSearch() {
        Log.i(TAG, "Opening Zhaopin for mobile job search");
        return openZhaopin();
    }

    private boolean tryOpenExternal(String value) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(value)));
            return true;
        } catch (ActivityNotFoundException | SecurityException exception) {
            Log.w(TAG, "No activity can handle Zhaopin fallback", exception);
            return false;
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void configureNativeSpeech() {
        textToSpeech = new TextToSpeech(this, status -> {
            textToSpeechReady = status == TextToSpeech.SUCCESS;
            if (!textToSpeechReady) return;
            textToSpeech.setLanguage(Locale.SIMPLIFIED_CHINESE);
            textToSpeech.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                @Override
                public void onStart(String utteranceId) {
                    notifySpeechEvent(utteranceId, "start");
                }

                @Override
                public void onDone(String utteranceId) {
                    notifySpeechEvent(utteranceId, "end");
                }

                @Override
                public void onError(String utteranceId) {
                    notifySpeechEvent(utteranceId, "error");
                }
            });
        });
    }

    private void notifySpeechEvent(String utteranceId, String event) {
        if (webView == null) return;
        String script = "window.__careerPilotNativeSpeechEvent && window.__careerPilotNativeSpeechEvent("
                + JSONObject.quote(utteranceId) + "," + JSONObject.quote(event) + ")";
        webView.post(() -> webView.evaluateJavascript(script, null));
    }

    private void installNativeSpeechShim(WebView view) {
        view.evaluateJavascript("""
                (() => {
                  if (!window.CareerPilotNativeSpeech || window.speechSynthesis) return;
                  const utterances = new Map();
                  let sequence = 0;
                  class NativeUtterance {
                    constructor(text) {
                      this.text = String(text || '');
                      this.lang = 'zh-CN';
                      this.rate = 1;
                      this.pitch = 1;
                      this.voice = null;
                      this.onstart = null;
                      this.onend = null;
                      this.onerror = null;
                    }
                  }
                  const synthesis = {
                    _speaking: false,
                    get speaking() { return this._speaking; },
                    getVoices() { return []; },
                    cancel() {
                      window.CareerPilotNativeSpeech.cancel();
                      this._speaking = false;
                      utterances.clear();
                    },
                    speak(utterance) {
                      const id = `careerpilot-${Date.now()}-${++sequence}`;
                      utterances.set(id, utterance);
                      this._speaking = true;
                      window.CareerPilotNativeSpeech.speak(
                        id,
                        String(utterance.text || ''),
                        Number(utterance.rate || 1),
                        Number(utterance.pitch || 1)
                      );
                    }
                  };
                  window.__careerPilotNativeSpeechEvent = (id, event) => {
                    const utterance = utterances.get(id);
                    if (!utterance) return;
                    if (event === 'start') utterance.onstart?.();
                    if (event === 'end' || event === 'error') {
                      synthesis._speaking = false;
                      utterances.delete(id);
                      if (event === 'end') utterance.onend?.();
                      else utterance.onerror?.();
                    }
                  };
                  window.SpeechSynthesisUtterance ||= NativeUtterance;
                  window.speechSynthesis = synthesis;
                })();
                """, null);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    protected void onDestroy() {
        if (textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.shutdown();
            textToSpeech = null;
        }
        if (webView != null) {
            webView.stopLoading();
            webView.setWebChromeClient(null);
            webView.setWebViewClient(null);
            webView.destroy();
        }
        super.onDestroy();
    }

    private class NativeSpeechInterface {
        @JavascriptInterface
        public void speak(String utteranceId, String text, double rate, double pitch) {
            runOnUiThread(() -> {
                if (!textToSpeechReady || textToSpeech == null || text.trim().isEmpty()) {
                    notifySpeechEvent(utteranceId, "error");
                    return;
                }
                textToSpeech.setSpeechRate((float) Math.max(0.5, Math.min(rate, 2.0)));
                textToSpeech.setPitch((float) Math.max(0.5, Math.min(pitch, 2.0)));
                Bundle parameters = new Bundle();
                int result = textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, parameters, utteranceId);
                if (result == TextToSpeech.ERROR) notifySpeechEvent(utteranceId, "error");
            });
        }

        @JavascriptInterface
        public boolean isReady() {
            return textToSpeechReady;
        }

        @JavascriptInterface
        public void cancel() {
            runOnUiThread(() -> {
                if (textToSpeech != null) textToSpeech.stop();
            });
        }
    }

    private class NativeAppsInterface {
        @JavascriptInterface
        public String openZhaopin() {
            return MainActivity.this.openZhaopin();
        }

        @JavascriptInterface
        public String openZhaopinSearch() {
            return MainActivity.this.openZhaopinSearch();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST || fileCallback == null) return;
        Uri[] results = null;
        if (resultCode == RESULT_OK && data != null) {
            ClipData clipData = data.getClipData();
            if (clipData != null) {
                results = new Uri[clipData.getItemCount()];
                for (int index = 0; index < clipData.getItemCount(); index++) {
                    results[index] = clipData.getItemAt(index).getUri();
                }
            } else if (data.getData() != null) {
                results = new Uri[]{data.getData()};
            }
        }
        fileCallback.onReceiveValue(results);
        fileCallback = null;
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != MICROPHONE_PERMISSION_REQUEST || pendingWebPermission == null) return;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            pendingWebPermission.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
        } else {
            pendingWebPermission.deny();
            Toast.makeText(this, R.string.microphone_denied, Toast.LENGTH_LONG).show();
        }
        pendingWebPermission = null;
    }

    private class CareerPilotWebViewClient extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            if (isAppUrl(uri)) return false;
            openExternal(uri.toString());
            return true;
        }

        @Override
        public void onPageStarted(WebView view, String url, Bitmap favicon) {
            progressBar.setVisibility(View.VISIBLE);
            errorView.setVisibility(View.GONE);
            webView.setVisibility(View.VISIBLE);
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            progressBar.setVisibility(View.GONE);
            CookieManager.getInstance().flush();
            view.evaluateJavascript("document.documentElement.classList.add('android-app')", null);
            installNativeSpeechShim(view);
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (request.isForMainFrame()) showNetworkError();
        }

    }

    private class CareerPilotWebChromeClient extends WebChromeClient {
        @Override
        public void onProgressChanged(WebView view, int progress) {
            progressBar.setProgress(progress);
            progressBar.setVisibility(progress >= 100 ? View.GONE : View.VISIBLE);
        }

        @Override
        public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> callback, FileChooserParams params) {
            if (fileCallback != null) fileCallback.onReceiveValue(null);
            fileCallback = callback;
            Intent intent = params.createIntent();
            intent.setAction(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE);
            try {
                startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                return true;
            } catch (ActivityNotFoundException exception) {
                fileCallback = null;
                Toast.makeText(MainActivity.this, R.string.file_picker_unavailable, Toast.LENGTH_SHORT).show();
                return false;
            }
        }

        @Override
        public void onPermissionRequest(PermissionRequest request) {
            runOnUiThread(() -> {
                if (!isAppUrl(request.getOrigin())) {
                    request.deny();
                    return;
                }
                boolean asksForAudio = false;
                for (String resource : request.getResources()) {
                    if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)) asksForAudio = true;
                }
                if (!asksForAudio) {
                    request.deny();
                    return;
                }
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                    request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                } else {
                    pendingWebPermission = request;
                    requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, MICROPHONE_PERMISSION_REQUEST);
                }
            });
        }
    }
}

package com.dsh.wordbook;

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.speech.tts.Voice;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.util.Locale;
import java.util.Set;

public class MainActivity extends Activity {
    private WebView wv;
    private TextToSpeech tts;
    private volatile boolean ttsReady = false;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        wv = new WebView(this);
        WebSettings s = wv.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        if (Build.VERSION.SDK_INT >= 21) {
            s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        }
        wv.setWebViewClient(new WebViewClient());
        wv.setWebChromeClient(new WebChromeClient());
        wv.setBackgroundColor(0xFFF4EFE4);

        // WebView 里没有可用的 Web Speech API，用系统 TextToSpeech 桥接
        tts = new TextToSpeech(this, new TextToSpeech.OnInitListener() {
            @Override
            public void onInit(int status) {
                if (status == TextToSpeech.SUCCESS) {
                    int r = tts.setLanguage(Locale.US);
                    ttsReady = r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED;
                    pickBestVoice(Locale.US);
                    tts.setSpeechRate(0.9f);
                    tts.setPitch(1.0f);
                } else {
                    ttsReady = false;
                }
            }
        });
        wv.addJavascriptInterface(new TtsBridge(), "AndroidTTS");

        setContentView(wv);
        wv.loadUrl("file:///android_asset/vocab.html");
    }

    /** 在同语言音色里挑一个尽量自然的：本地高质量优先，其次 Google/Microsoft/Samsung。 */
    private void pickBestVoice(Locale want) {
        if (tts == null || Build.VERSION.SDK_INT < 21) return;
        try {
            Set<Voice> voices = tts.getVoices();
            if (voices == null || voices.isEmpty()) return;
            Voice best = null;
            int bestScore = Integer.MIN_VALUE;
            for (Voice v : voices) {
                if (v == null || v.getLocale() == null) continue;
                if (!"en".equals(v.getLocale().getLanguage())) continue;
                if (v.getFeatures() != null && v.getFeatures().contains("notInstalled")) continue;
                String n = v.getName() == null ? "" : v.getName().toLowerCase(Locale.US);
                int sc = 0;
                if (!want.getCountry().isEmpty() && want.getCountry().equalsIgnoreCase(v.getLocale().getCountry())) sc += 4;
                if (n.contains("google")) sc += 3;
                if (n.contains("microsoft")) sc += 3;
                if (n.contains("samsung")) sc += 2;
                if (n.contains("pico")) sc -= 6;
                if (v.getQuality() >= Voice.QUALITY_HIGH) sc += 3;
                else if (v.getQuality() >= Voice.QUALITY_NORMAL) sc += 1;
                if (v.isNetworkConnectionRequired()) sc += 1;
                if (v.getLatency() == Voice.LATENCY_LOW) sc += 1;
                if (sc > bestScore) { bestScore = sc; best = v; }
            }
            if (best != null) tts.setVoice(best);
        } catch (Exception ignored) { }
    }

    private void setLanguageAndVoice(Locale loc) {
        if (tts == null) return;
        int r = tts.setLanguage(loc);
        ttsReady = r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED;
        pickBestVoice(loc);
    }

    public class TtsBridge {
        @JavascriptInterface
        public boolean ready() {
            return ttsReady;
        }

        @JavascriptInterface
        public void speak(final String text) {
            if (!ttsReady || text == null || tts == null) return;
            if (Build.VERSION.SDK_INT >= 21) {
                tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "wordbook");
            } else {
                tts.speak(text, TextToSpeech.QUEUE_FLUSH, null);
            }
        }

        @JavascriptInterface
        public void setAccent(String accent) {
            if (tts == null) return;
            setLanguageAndVoice("uk".equalsIgnoreCase(accent) ? Locale.UK : Locale.US);
        }

        @JavascriptInterface
        public void setRate(float rate) {
            if (tts == null) return;
            tts.setSpeechRate(Math.max(0.5f, Math.min(1.5f, rate)));
        }

        @JavascriptInterface
        public void setPitch(float pitch) {
            if (tts == null) return;
            tts.setPitch(Math.max(0.5f, Math.min(1.5f, pitch)));
        }

        @JavascriptInterface
        public void stop() {
            if (tts != null) tts.stop();
        }
    }

    @Override
    public void onBackPressed() {
        if (wv != null && wv.canGoBack()) wv.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (wv != null) wv.onPause();
        if (tts != null) tts.stop();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (wv != null) wv.onResume();
    }

    @Override
    protected void onDestroy() {
        if (tts != null) {
            tts.stop();
            tts.shutdown();
            tts = null;
        }
        ttsReady = false;
        super.onDestroy();
    }
}

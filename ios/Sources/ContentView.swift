import SwiftUI
import WebKit
import AVFoundation
import UIKit

/// 用 WKWebView 装同一份网页；语音走系统 AVSpeechSynthesizer，
/// 通过 window.AndroidTTS 这个“同名桥”复用网页里已有的发音逻辑。
struct ContentView: View {
    var body: some View {
        WebViewContainer()
            .background(Color(red: 0.93, green: 0.95, blue: 0.97))
    }
}

struct WebViewContainer: UIViewRepresentable {
    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.allowsInlineMediaPlayback = true
        cfg.mediaTypesRequiringUserActionForPlayback = []
        let ucc = cfg.userContentController
        ucc.add(context.coordinator, name: "tts")
        ucc.add(context.coordinator, name: "ttsStop")

        // 桥接脚本：网页检测到 window.AndroidTTS 就会优先用它发音
        let bridge = """
        window.AndroidTTS = {
          ready: function () { return true; },
          speak: function (t) { window.webkit.messageHandlers.tts.postMessage(String(t || '')); },
          stop: function () { window.webkit.messageHandlers.ttsStop.postMessage(''); }
        };
        """
        ucc.addUserScript(WKUserScript(source: bridge, injectionTime: .atDocumentStart, forMainFrameOnly: true))

        let web = WKWebView(frame: .zero, configuration: cfg)
        web.isOpaque = false
        web.backgroundColor = .clear
        web.scrollView.bounces = false
        web.scrollView.contentInsetAdjustmentBehavior = .never
        web.navigationDelegate = context.coordinator
        web.uiDelegate = context.coordinator

        if let url = Bundle.main.url(forResource: "vocab", withExtension: "html", subdirectory: "www") {
            web.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        }
        return web
    }

    func updateUIView(_ web: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
        private let synth = AVSpeechSynthesizer()

        func userContentController(_ uc: WKUserContentController, didReceive message: WKScriptMessage) {
            switch message.name {
            case "tts":
                guard let text = message.body as? String, !text.isEmpty else { return }
                if synth.isSpeaking { synth.stopSpeaking(at: .immediate) }
                let utt = AVSpeechUtterance(string: text)
                utt.voice = AVSpeechSynthesisVoice(language: "en-US")
                utt.rate = 0.46
                synth.speak(utt)
            case "ttsStop":
                if synth.isSpeaking { synth.stopSpeaking(at: .immediate) }
            default: break
            }
        }

        // 外链用系统浏览器打开
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if let url = navigationAction.request.url,
               navigationAction.navigationType == .linkActivated,
               url.scheme == "http" || url.scheme == "https" {
                UIApplication.shared.open(url)
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }
    }
}

import { webview } from '@kit.ArkWeb';
import { SpeechService } from '../common/SpeechService';

/**
 * 网页通过 window.AndroidTTS 调用的对象。
 * 方法名必须与 web/app.template.html 里的 NATIVE_TTS 约定一致：
 * ready / speak / stop / setAccent / setRate。
 */
class TtsBridge {
  private speech: SpeechService;

  constructor(speech: SpeechService) {
    this.speech = speech;
  }

  ready(): boolean {
    return this.speech.isReady();
  }

  speak(text: string): boolean {
    return this.speech.speak(text);
  }

  stop(): void {
    this.speech.stop();
  }

  setAccent(accent: string): void {
    this.speech.setAccent(accent);
  }

  setRate(rate: number): void {
    this.speech.setRate(rate);
  }
}

@Entry
@Component
struct Index {
  private controller: webview.WebviewController = new webview.WebviewController();
  private speech: SpeechService = new SpeechService();
  private bridge: TtsBridge = new TtsBridge(this.speech);

  aboutToAppear(): void {
    this.speech.init();
  }

  aboutToDisappear(): void {
    this.speech.shutdown();
  }

  onBackPress(): boolean {
    if (this.controller.accessBackward()) {
      this.controller.backward();
      return true;
    }
    return false;
  }

  build() {
    Column() {
      Web({ src: $rawfile('vocab.html'), controller: this.controller })
        .javaScriptAccess(true)
        .domStorageAccess(true)
        .fileAccess(true)
        .databaseAccess(true)
        .mixedMode(MixedMode.All)
        .javaScriptProxy({
          object: this.bridge,
          name: 'AndroidTTS',
          methodList: ['ready', 'speak', 'stop', 'setAccent', 'setRate'],
          controller: this.controller
        })
    }
    .width('100%')
    .height('100%')
  }
}

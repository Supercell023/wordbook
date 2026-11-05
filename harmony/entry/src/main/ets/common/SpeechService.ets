import { textToSpeech } from '@kit.CoreSpeechKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { hilog } from '@kit.PerformanceAnalysisKit';

const TAG: string = 'WordbookTTS';
const DOMAIN: number = 0x0000;

/**
 * HarmonyOS NEXT 的系统语音桥。
 *
 * 网页里的 window.AndroidTTS 会调用这里的方法，名字保持和 Android 版一致，
 * 这样 web/app.template.html 不需要为鸿蒙单独改一套发音逻辑。
 *
 * Core Speech Kit 的 createEngine 官方只写支持中文，但英文/日文文本可以
 * 直接读出来；它只在真机上可用，模拟器会创建失败。
 */
export class SpeechService {
  private engine: textToSpeech.TextToSpeechEngine | null = null;
  private initializing: boolean = false;
  private rate: number = 0.9;
  private accent: string = 'us';

  init(): void {
    if (this.engine !== null || this.initializing) {
      return;
    }
    this.initializing = true;
    const params: textToSpeech.CreateEngineParams = {
      language: 'zh-CN',
      person: 0,
      online: 1,
      extraParams: {}
    };
    textToSpeech.createEngine(params, (err: BusinessError, engine: textToSpeech.TextToSpeechEngine) => {
      this.initializing = false;
      if (err) {
        hilog.error(DOMAIN, TAG, 'createEngine failed: %{public}s', `${err.code}`);
        return;
      }
      this.engine = engine;
      hilog.info(DOMAIN, TAG, 'createEngine succeeded');
    });
  }

  isReady(): boolean {
    return this.engine !== null;
  }

  speak(text: string): boolean {
    if (!text || text.trim().length === 0) {
      return false;
    }
    if (this.engine === null) {
      this.init();
      return false;
    }
    const requestId: string = `wordbook-${Date.now()}`;
    const languageContext: string = this.accent === 'uk' ? 'en-GB' : 'en-US';
    try {
      this.engine.speak(text, {
        requestId: requestId,
        extraParams: {
          'speed': this.rate,
          'volume': 1,
          'pitch': 1,
          'languageContext': languageContext
        }
      });
      return true;
    } catch (err) {
      hilog.error(DOMAIN, TAG, 'speak failed: %{public}s', JSON.stringify(err));
      return false;
    }
  }

  stop(): void {
    if (this.engine !== null) {
      this.engine.stop();
    }
  }

  setAccent(accent: string): void {
    this.accent = accent;
  }

  setRate(rate: number): void {
    this.rate = rate;
  }

  shutdown(): void {
    if (this.engine !== null) {
      this.engine.shutdown();
      this.engine = null;
    }
  }
}

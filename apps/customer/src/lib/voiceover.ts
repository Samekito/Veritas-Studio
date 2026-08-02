// The video model returns silent footage and the voiceover is a separate TTS
// asset, so the two are played as one piece and have to be rate-matched.
export const RATE_MIN = 0.0625; // browsers throw NotSupportedError outside this range
export const RATE_MAX = 16;

/** Speech seconds per picture second.
 *
 * Only ever compresses an over-long voiceover to fit the clip — never stretches
 * a short one, since slowing a read below 1x makes it drawl. A voiceover that
 * ends before the picture does is normal for an ad and plays at natural speed.
 */
export function voiceoverRate(audioDuration: number, videoDuration: number): number {
  if (!audioDuration || !videoDuration || !isFinite(audioDuration) || !isFinite(videoDuration)) {
    return 1;
  }
  return Math.min(RATE_MAX, Math.max(1, audioDuration / videoDuration));
}

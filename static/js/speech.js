/**
 * Accessible SpeechSynthesis helper to read summaries aloud.
 */

let currentUtterance = null;

export function speakText(text, lang = "en") {
  if (!("speechSynthesis" in window)) {
    alert("Speech synthesis is not supported in this browser.");
    return false;
  }

  // If currently speaking, stop
  if (window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    if (currentUtterance && currentUtterance._text === text) {
      currentUtterance = null;
      return false; // stopped
    }
  }

  const utterance = new SpeechSynthesisUtterance(text);
  utterance._text = text;

  // Language mapping
  if (lang === "ta") {
    utterance.lang = "ta-IN";
  } else if (lang === "hi") {
    utterance.lang = "hi-IN";
  } else {
    utterance.lang = "en-US";
  }

  utterance.rate = 0.95;
  utterance.onend = () => {
    currentUtterance = null;
  };
  utterance.onerror = () => {
    currentUtterance = null;
  };

  currentUtterance = utterance;
  window.speechSynthesis.speak(utterance);
  return true; // started speaking
}

export function stopSpeaking() {
  if ("speechSynthesis" in window && window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    currentUtterance = null;
  }
}

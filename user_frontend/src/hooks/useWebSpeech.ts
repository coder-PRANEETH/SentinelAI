import { useState, useRef, useCallback, useEffect } from 'react';

export function useWebSpeech({ onTranscript }: { onTranscript: (text: string) => void }) {
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string>('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const recognitionRef = useRef<any>(null);
  const onTranscriptRef = useRef(onTranscript);

  // Keep ref up to date
  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        recognitionRef.current = new SpeechRecognition();
        recognitionRef.current.continuous = true;
        recognitionRef.current.interimResults = true;
        
        // Let the user manually stop
        let manualStop = false;

        recognitionRef.current.onstart = () => {
          setIsListening(true);
          setError('');
        };
        
        recognitionRef.current.onerror = (event: any) => {
          console.error('Speech recognition error', event.error);
          if (event.error === 'no-speech') {
            // Normal pause, do not kill the session or show an error
          } else if (event.error === 'audio-capture') {
            setError('Microphone disconnected or unavailable. Please check your device.');
            setIsListening(false);
          } else if (event.error === 'network') {
            // Ignore non-fatal network hiccups that Chrome usually recovers from
            // without actually killing the dictation stream.
          } else if (event.error === 'not-allowed' || event.error === 'permission-denied') {
            setError('Microphone access denied. Please check permissions.');
            setIsListening(false);
          } else if (event.error === 'aborted') {
            // Deliberate abort, no error needed
          } else {
            setError(`Recognition error: ${event.error}`);
            setIsListening(false);
          }
        };
        
        recognitionRef.current.onend = () => {
          setIsListening(false);
        };
        
        recognitionRef.current.onresult = (event: any) => {
          let finalTranscript = '';
          let currentInterim = '';
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              finalTranscript += event.results[i][0].transcript;
            } else {
              currentInterim += event.results[i][0].transcript;
            }
          }
          
          setInterimTranscript(currentInterim);
          
          if (finalTranscript) {
            onTranscriptRef.current(finalTranscript.trim());
          }
        };
      }
    }
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);

  const toggleListening = useCallback(() => {
    if (!recognitionRef.current) {
      setError('Browser does not support Speech Recognition.');
      return;
    }
    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
        // Sometimes continuous recognition needs aborting to fully stop immediately
        try { recognitionRef.current.abort(); } catch(e) {}
      }
      setIsListening(false);
      setInterimTranscript('');
    } else {
      try {
        recognitionRef.current.start();
      } catch (e) {
        console.error(e);
      }
    }
  }, [isListening]);

  return { isListening, error, interimTranscript, toggleListening };
}

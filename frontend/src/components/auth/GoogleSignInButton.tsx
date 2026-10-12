import { useEffect, useRef, useState } from "react";

import { ApiError } from "../../services/api";
import {
  getGoogleSignInChallenge,
  signInWithGoogleCredential,
} from "../../services/auth";
import type { AuthResponse } from "../../types/api";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            nonce: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: Record<string, string | number>,
          ) => void;
        };
      };
    };
  }
}

let googleScriptPromise: Promise<void> | null = null;

function loadGoogleIdentityScript(): Promise<void> {
  if (window.google?.accounts.id) return Promise.resolve();
  if (googleScriptPromise) return googleScriptPromise;

  const loading = new Promise<void>((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>(
      'script[src="https://accounts.google.com/gsi/client"]',
    );
    const script = existingScript ?? document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Google Sign-In could not be loaded."));
    if (!existingScript) document.head.append(script);
  }).catch((error: unknown) => {
    googleScriptPromise = null;
    throw error;
  });

  googleScriptPromise = loading;
  return loading;
}

export function GoogleSignInButton({
  onAuthenticated,
}: {
  onAuthenticated: (result: AuthResponse) => void;
}) {
  const buttonRef = useRef<HTMLDivElement>(null);
  const onAuthenticatedRef = useRef(onAuthenticated);
  const [error, setError] = useState<string | null>(null);
  const [isSigningIn, setIsSigningIn] = useState(false);

  useEffect(() => {
    onAuthenticatedRef.current = onAuthenticated;
  }, [onAuthenticated]);

  useEffect(() => {
    let active = true;
    const button = buttonRef.current;

    void (async () => {
      try {
        const challenge = await getGoogleSignInChallenge();
        await loadGoogleIdentityScript();
        if (!active || !window.google) return;

        window.google.accounts.id.initialize({
          client_id: challenge.client_id,
          nonce: challenge.nonce,
          callback: (credentialResponse) => {
            if (!active) return;
            setIsSigningIn(true);
            setError(null);
            void signInWithGoogleCredential(
              credentialResponse.credential,
              challenge.nonce,
            )
              .then((result) => {
                if (active) onAuthenticatedRef.current(result);
              })
              .catch((reason: unknown) => {
                if (active) {
                  setError(
                    reason instanceof ApiError
                      ? reason.detail
                      : "Google Sign-In could not be completed. Please try again.",
                  );
                }
              })
              .finally(() => {
                if (active) setIsSigningIn(false);
              });
          },
        });

        if (buttonRef.current) {
          window.google.accounts.id.renderButton(buttonRef.current, {
            theme: "outline",
            size: "large",
            shape: "pill",
            text: "continue_with",
            width: Math.min(buttonRef.current.clientWidth, 400),
          });
        }
      } catch (reason) {
        if (active) {
          setError(
            reason instanceof ApiError
              ? reason.detail
              : "Google Sign-In could not be loaded. Please try again.",
          );
        }
      }
    })();

    return () => {
      active = false;
      button?.replaceChildren();
    };
  }, []);

  return (
    <div className="space-y-2">
      <div
        ref={buttonRef}
        className={`flex min-h-11 justify-center ${isSigningIn ? "pointer-events-none opacity-60" : ""}`}
        aria-label="Continue with Google"
      />
      {isSigningIn && (
        <p className="text-center text-sm text-slate-500" role="status">
          Signing in with Google...
        </p>
      )}
      {error && (
        <p className="text-center text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

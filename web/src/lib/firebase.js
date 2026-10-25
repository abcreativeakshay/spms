import { initializeApp } from "firebase/app";
import { getAuth, signInWithEmailAndPassword, signOut } from "firebase/auth";

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
};

export const firebaseEnabled = Boolean(config.apiKey && config.projectId);

export const firebaseAuth = firebaseEnabled ? getAuth(initializeApp(config)) : null;

export async function signInWithFirebase(email, password) {
  if (!firebaseAuth) throw new Error("Firebase is not configured for this build.");
  const credential = await signInWithEmailAndPassword(firebaseAuth, email, password);
  return credential.user.getIdToken();
}

export async function signOutOfFirebase() {
  if (firebaseAuth) {
    try {
      await signOut(firebaseAuth);
    } catch {
      // Ignore; local token is cleared by the auth context.
    }
  }
}

import { getApp, getApps, initializeApp } from "firebase/app";
import {
  getMessaging,
  isSupported,
  type Messaging,
} from "firebase/messaging";

const firebaseConfig = {
  apiKey: "AIzaSyAllxR7y4EYiIEuOHm8O-T1v6Av_-kYBdU",
  authDomain: "skaliapp-e0dee.firebaseapp.com",
  projectId: "skaliapp-e0dee",
  storageBucket: "skaliapp-e0dee.firebasestorage.app",
  messagingSenderId: "572913753788",
  appId: "1:572913753788:web:ed03e19953c82301e93ab9",
  measurementId: "G-RJ3WNHFE7E",
};

export const firebaseApp =
  getApps().length > 0
    ? getApp()
    : initializeApp(firebaseConfig);

/**
 * Returns Firebase Messaging when the browser supports it.
 *
 * Returns null when messaging is unsupported, such as in
 * browsers or environments without the required APIs.
 */
export async function getWebMessaging(): Promise<Messaging | null> {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const supported = await isSupported();

    if (!supported) {
      return null;
    }

    return getMessaging(firebaseApp);
  } catch (error) {
    console.error(
      "[Firebase] Messaging is unavailable:",
      error
    );

    return null;
  }
}

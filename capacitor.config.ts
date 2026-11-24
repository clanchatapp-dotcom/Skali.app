import { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'app.skali.mobile',
  appName: 'Skali',
  webDir: 'dist',
  server: { androidScheme: 'https' },
  // iPhone: still show alerts while Skali is open.
  plugins: { PushNotifications: { presentationOptions: ['badge', 'sound', 'alert'] } },
}

export default config

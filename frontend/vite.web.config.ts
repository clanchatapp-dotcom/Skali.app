import path from 'path'
import { fileURLToPath } from 'url'
import base from '../vite.config'

// Web deploy build: ship the root app (/app/src — Content Streaming + OBS) into frontend/build.
const here = path.dirname(fileURLToPath(import.meta.url))

export default {
  ...base,
  root: path.resolve(here, '..'),
  envDir: here,
  build: { outDir: path.resolve(here, 'build'), emptyOutDir: true },
}

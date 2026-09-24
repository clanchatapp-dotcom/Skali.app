import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { api, getToken, wsDmUrl } from '../lib/api'
import { Avatar, Linkify } from '../lib/ui'
import { useAuth } from '../lib/auth'
import CallModal from '../components/CallModal'
import RoleBadge from '../components/RoleBadge'
import AccountBadge from '../components/AccountBadge'
import {
  secureOn,
  secureOff
} from '../lib/privacyScreen'
import {
  Send,
  Phone,
  Video,
  Lock,
  ArrowLeft,
  Loader2,
  Bookmark,
  Trash2,
  Pin,
  Mic,
  Square,
  Users,
  ChevronRight,
  Eye,
  Flame,
  Image as ImageIcon,
  X,
  Smile,
  Pencil,
  Plus,
  Camera
} from 'lucide-react'

export default function Messages() {
  const { handle } = useParams()
  const nav = useNavigate()
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const jumpId = searchParams.get('jump')
  const [flashId, setFlashId] = useState<string | null>(null)

  const [threads, setThreads] = useState<any[]>([])
  const [thread, setThread] = useState<any>(null)
  const [msgs, setMsgs] = useState<any[]>([])

  // Jump to a specific message when arriving from the conversation-info search
  // (route: /messages/:handle?jump=<id>). Scrolls it into view and briefly flashes it.
  useEffect(() => {
    if (!jumpId || msgs.length === 0) return
    const el = document.getElementById(`msg-${jumpId}`)
    if (!el) return
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setFlashId(jumpId)
    const t = setTimeout(() => setFlashId(null), 2200)
    return () => clearTimeout(t)
  }, [jumpId, msgs])

  const [text, setText] = useState('')
  const [call, setCall] =
    useState<{
      room: string
      media: 'audio' | 'video'
    } | null>(null)
  const [loading, setLoading] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const endRef = useRef<HTMLDivElement | null>(null)
  const seen = useRef<Set<string>>(new Set())

  useEffect(() => {
    api.dmThreads().then(setThreads).catch(() => {})
  }, [handle])

  // Screenshot protection: block screenshots/recording while a DM thread is open.
  useEffect(() => {
    if (!handle) return

    secureOn()

    return () => {
      secureOff()
    }
  }, [handle])

  useEffect(() => {
    if (!handle) {
      setThread(null)
      return
    }

    let stop = false

    seen.current = new Set()
    setLoading(true)

    ;(async () => {
      try {
        const h = await api.dmHistory(handle)

        if (stop) return

        setThread(h)
        h.messages.forEach((m: any) =>
          seen.current.add(m.id)
        )
        setMsgs(h.messages)
        setLoading(false)
      } catch (e: any) {
        if (stop) return

        setLoading(false)
        alert(
          e?.message ||
            'Could not load messages'
        )
      }
    })()

    const connect = () => {
      const t = getToken()

      if (!t) return

      const ws = new WebSocket(
        wsDmUrl(handle, t)
      )

      wsRef.current = ws

      ws.onmessage = ev => {
        try {
          const d = JSON.parse(ev.data)

          if (
            d.type === 'dm' &&
            !seen.current.has(d.message.id)
          ) {
            seen.current.add(d.message.id)

            setMsgs(p => [
              ...p,
              {
                ...d.message,
                mine:
                  d.message.sender_id ===
                  user?.id
              }
            ])
          }

          if (d.type === 'dm_deleted') {
            setMsgs(p =>
              p.map(m =>
                m.id === d.id
                  ? {
                      ...m,
                      deleted: true,
                      media_url: null,
                      text: 'This message was deleted'
                    }
                  : m
              )
            )
          }

          if (d.type === 'dm_pin') {
            setMsgs(p =>
              p.map(m =>
                m.id === d.id
                  ? {
                      ...m,
                      pinned: d.pinned
                    }
                  : m
              )
            )
          }

          if (d.type === 'dm_viewed') {
            setMsgs(p =>
              p.map(m =>
                m.id === d.id
                  ? {
                      ...m,
                      view_once_viewed: true
                    }
                  : m
              )
            )
          }

          if (d.type === 'call_declined') {
            setCall(null)
            alert(
              `@${d.from} declined the call`
            )
          }
        } catch {}
      }

      ws.onclose = () => {
        if (!stop) {
          setTimeout(connect, 1500)
        }
      }
    }

    connect()

    return () => {
      stop = true
      wsRef.current?.close()
    }
  }, [handle])

  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: 'smooth'
    })
  }, [msgs])

  const send = async (e: React.FormEvent) => {
    e.preventDefault()

    const body = text.trim()

    if (!body || !handle) return

    setText('')

    try {
      const m = await api.dmSend(
        handle,
        body
      )

      if (!seen.current.has(m.id)) {
        seen.current.add(m.id)
        setMsgs(p => [...p, m])
      }
    } catch (err: any) {
      alert(err.message)
      setText(body)
    }
  }

  const recRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const recStart = useRef<number>(0)

  const [recording, setRecording] =
    useState(false)

  const [busy, setBusy] =
    useState(false)

  const startRec = async () => {
    try {
      const stream =
        await navigator.mediaDevices.getUserMedia(
          {
            audio: true
          }
        )

      const mr = new MediaRecorder(stream)

      recRef.current = mr
      chunksRef.current = []
      recStart.current = Date.now()

      mr.ondataavailable = e => {
        chunksRef.current.push(e.data)
      }

      mr.onstop = async () => {
        stream
          .getTracks()
          .forEach(t => t.stop())

        const blob = new Blob(
          chunksRef.current,
          {
            type: 'audio/webm'
          }
        )

        const dur = Math.round(
          (Date.now() -
            recStart.current) /
            1000
        )

        if (dur < 1 || !handle) return

        setBusy(true)

        try {
          const { signed_url } =
            await api.upload(
              new File(
                [blob],
                `voice-${Date.now()}.webm`,
                {
                  type: 'audio/webm'
                }
              )
            )

          const m =
            await api.sendDmMedia(
              handle,
              signed_url,
              'audio',
              dur
            )

          if (!seen.current.has(m.id)) {
            seen.current.add(m.id)

            setMsgs(p => [
              ...p,
              m
            ])
          }
        } catch (e: any) {
          alert(
            e.message ||
              'Could not send voice message'
          )
        }

        setBusy(false)
      }

      mr.start()
      setRecording(true)
    } catch {
      alert(
        'Microphone permission needed to record a voice message.'
      )
    }
  }

  const stopRec = () => {
    recRef.current?.stop()
    setRecording(false)
  }

  /*
   * Message actions / long press
   */

  const [messageActions, setMessageActions] =
    useState<string | null>(null)

  const longPressTimer =
    useRef<ReturnType<typeof setTimeout> | null>(
      null
    )

  const longPressStart =
    useRef<{
      x: number
      y: number
    } | null>(null)

  const startLongPress = (
    id: string,
    e?: React.PointerEvent
  ) => {
    if (e) {
      longPressStart.current = {
        x: e.clientX,
        y: e.clientY
      }
    }

    if (longPressTimer.current) {
      clearTimeout(
        longPressTimer.current
      )
    }

    longPressTimer.current =
      setTimeout(() => {
        setMessageActions(id)
        longPressTimer.current = null
      }, 600)
  }

  const cancelLongPress = () => {
    if (longPressTimer.current) {
      clearTimeout(
        longPressTimer.current
      )

      longPressTimer.current = null
    }

    longPressStart.current = null
  }

  const handleMessagePointerMove = (
    e: React.PointerEvent
  ) => {
    if (!longPressStart.current) return

    const dx =
      e.clientX -
      longPressStart.current.x

    const dy =
      e.clientY -
      longPressStart.current.y

    if (
      Math.sqrt(
        dx * dx + dy * dy
      ) > 10
    ) {
      cancelLongPress()
    }
  }

  const togglePin = async (
    id: string
  ) => {
    try {
      const r =
        await api.pinDm(
          handle!,
          id
        )

      setMsgs(x =>
        x.map(m =>
          m.id === id
            ? {
                ...m,
                pinned: r.pinned
              }
            : m
        )
      )

      return r
    } catch {
      return null
    }
  }

  const deleteMessage = async (
    id: string
  ) => {
    if (!handle) return

    try {
      await api.deleteDm(
        handle,
        id
      )

      setMsgs(x =>
        x.map(y =>
          y.id === id
            ? {
                ...y,
                deleted: true,
                media_url: null,
                text: 'This message was deleted'
              }
            : y
        )
      )

      setMessageActions(null)
    } catch (e: any) {
      alert(
        e?.message ||
          'Could not delete message'
      )
    }
  }

  const [gifOpen, setGifOpen] =
    useState(false)

  const [gifs, setGifs] =
    useState<any[]>([])

  const [gifQ, setGifQ] =
    useState('')

  const [viewOnce, setViewOnce] =
    useState(false)

  const [noSave, setNoSave] =
    useState(false)

  const [pending, setPending] =
    useState<{
      url: string
      media_type: string
    } | null>(null)

  const [stickers, setStickers] =
    useState<any[]>([])

  const [stickerOpen, setStickerOpen] =
    useState(false)

  const [uploadingSticker, setUploadingSticker] =
    useState(false)

  const stickerRef =
    useRef<HTMLInputElement | null>(null)

  const loadStickers = async () => {
    try {
      setStickers(
        await api.listStickers()
      )
    } catch {}
  }

  useEffect(() => {
    loadStickers()
  }, [])

  const onStickerUpload = async (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const f =
      e.target.files?.[0]

    if (!f) return

    setUploadingSticker(true)

    try {
      const { signed_url } =
        await api.upload(f)

      await api.addSticker(
        signed_url
      )

      await loadStickers()
    } catch (err: any) {
      alert(
        err.message ||
          'Could not add sticker'
      )
    }

    setUploadingSticker(false)

    if (stickerRef.current) {
      stickerRef.current.value = ''
    }
  }

  const sendSticker = async (
    url: string
  ) => {
    if (!handle) return

    setStickerOpen(false)

    try {
      const m =
        await api.sendDmMedia(
          handle,
          url,
          'sticker',
          undefined,
          undefined,
          false,
          true
        )

      if (!seen.current.has(m.id)) {
        seen.current.add(m.id)

        setMsgs(p => [
          ...p,
          m
        ])
      }
    } catch (e: any) {
      alert(
        e?.message ||
          'Could not send sticker'
      )
    }
  }

  const removeSticker = async (
    id: string
  ) => {
    try {
      await api.deleteSticker(id)
      await loadStickers()
    } catch {}
  }

  const sendBlobSticker = async (
    file: File
  ) => {
    if (
      !handle ||
      !file ||
      !file.type.startsWith(
        'image/'
      )
    ) {
      return
    }

    try {
      const { signed_url } =
        await api.upload(file)

      await sendSticker(
        signed_url
      )
    } catch (e: any) {
      alert(
        e?.message ||
          'Could not send that sticker'
      )
    }
  }

  const onComposerPaste = (
    e: React.ClipboardEvent
  ) => {
    const items =
      e.clipboardData?.items ||
      []

    for (
      const it of items as any
    ) {
      if (
        it.kind === 'file' &&
        it.type.startsWith(
          'image/'
        )
      ) {
        const f =
          it.getAsFile()

        if (f) {
          e.preventDefault()
          sendBlobSticker(f)
        }

        return
      }
    }
  }

  const onComposerDrop = (
    e: React.DragEvent
  ) => {
    const f =
      e.dataTransfer?.files?.[0]

    if (
      f &&
      f.type.startsWith(
        'image/'
      )
    ) {
      e.preventDefault()
      sendBlobSticker(f)
    }
  }

  useEffect(() => {
    const onKbSticker = (
      e: any
    ) => {
      const dataUrl: string =
        e?.detail

      if (!dataUrl || !handle)
        return

      fetch(dataUrl)
        .then(r => r.blob())
        .then(b => {
          const ext =
            (
              b.type.split(
                '/'
              )[1] ||
              'png'
            ).split('+')[0]

          sendBlobSticker(
            new File(
              [b],
              `sticker.${ext}`,
              {
                type:
                  b.type ||
                  'image/png'
              }
            )
          )
        })
        .catch(() => {})
    }

    window.addEventListener(
      'skaliKeyboardSticker',
      onKbSticker as any
    )

    return () =>
      window.removeEventListener(
        'skaliKeyboardSticker',
        onKbSticker as any
      )
  }, [handle])

  const editNickname =
    async () => {
      if (!thread?.peer) return

      const cur =
        thread.peer.nickname ||
        ''

      const next =
        window.prompt(
          `Private nickname for ${thread.peer.display_name} (only you see it). Leave blank to clear.`,
          cur
        )

      if (next === null) return

      const nick =
        next.trim()

      try {
        await api.setNickname(
          thread.peer.handle,
          nick
        )

        setThread((t: any) =>
          t
            ? {
                ...t,
                peer: {
                  ...t.peer,
                  nickname:
                    nick || null
                }
              }
            : t
        )

        setThreads(ts =>
          ts.map(t =>
            t.user?.handle ===
            thread.peer.handle
              ? {
                  ...t,
                  user: {
                    ...t.user,
                    nickname:
                      nick || null
                  }
                }
              : t
          )
        )
      } catch (e: any) {
        alert(
          e.message ||
            'Could not set nickname'
        )
      }
    }

  /*
   * Photo / media viewer
   */

  const [viewer, setViewer] =
    useState<{
      url: string
      type: string
      allowSave: boolean
      viewOnce: boolean
    } | null>(null)

  const [uploadingImg, setUploadingImg] =
    useState(false)

  const imgRef =
    useRef<HTMLInputElement | null>(null)

  /*
   * Swipe-to-close state for the
   * full-screen media viewer.
   */

  const viewerTouchStart =
    useRef<{
      x: number
      y: number
    } | null>(null)

  const viewerTouchCurrent =
    useRef<{
      x: number
      y: number
    } | null>(null)

  const [viewerDragY, setViewerDragY] =
    useState(0)

  const [viewerDragging, setViewerDragging] =
    useState(false)

  const openMediaViewer = (
    url: string,
    type: string,
    allowSave = true
  ) => {
    setViewer({
      url,
      type,
      allowSave,
      viewOnce: false
    })

    setViewerDragY(0)
  }

  const closeViewer = () => {
    setViewer(null)
    setViewerDragY(0)
    setViewerDragging(false)
    viewerTouchStart.current = null
    viewerTouchCurrent.current = null
  }

  const onViewerPointerDown = (
    e: React.PointerEvent
  ) => {
    if (
      e.pointerType !== 'touch' &&
      e.pointerType !== 'pen'
    ) {
      return
    }

    viewerTouchStart.current = {
      x: e.clientX,
      y: e.clientY
    }

    viewerTouchCurrent.current = {
      x: e.clientX,
      y: e.clientY
    }

    setViewerDragging(true)
  }

  const onViewerPointerMove = (
    e: React.PointerEvent
  ) => {
    if (
      !viewerTouchStart.current
    ) {
      return
    }

    viewerTouchCurrent.current = {
      x: e.clientX,
      y: e.clientY
    }

    const dx =
      e.clientX -
      viewerTouchStart.current.x

    const dy =
      e.clientY -
      viewerTouchStart.current.y

    /*
     * Only move vertically when the
     * gesture is primarily vertical.
     */
    if (
      Math.abs(dy) >
      Math.abs(dx)
    ) {
      e.preventDefault()

      setViewerDragY(
        Math.max(
          0,
          dy
        )
      )
    }
  }

  const onViewerPointerUp = (
    e: React.PointerEvent
  ) => {
    if (
      !viewerTouchStart.current
    ) {
      return
    }

    const start =
      viewerTouchStart.current

    const dx =
      e.clientX - start.x

    const dy =
      e.clientY - start.y

    viewerTouchStart.current = null
    viewerTouchCurrent.current = null
    setViewerDragging(false)

    /*
     * Swipe down far enough to close.
     */
    if (
      dy > 120 &&
      Math.abs(dy) >
        Math.abs(dx) * 1.2
    ) {
      closeViewer()
      return
    }

    setViewerDragY(0)
  }

  const onViewerPointerCancel = () => {
    viewerTouchStart.current = null
    viewerTouchCurrent.current = null
    setViewerDragging(false)
    setViewerDragY(0)
  }

  const openGif = async () => {
    setGifOpen(o => !o)

    if (
      !gifOpen &&
      gifs.length === 0
    ) {
      try {
        setGifs(
          await api.giphySearch('')
        )
      } catch {}
    }
  }

  const searchGifs = async (
    query: string
  ) => {
    setGifQ(query)

    try {
      setGifs(
        await api.giphySearch(
          query
        )
      )
    } catch {}
  }

  const sendGif = (
    url: string
  ) => {
    if (!handle) return

    setGifOpen(false)
    setViewOnce(false)
    setNoSave(false)

    setPending({
      url,
      media_type: 'image'
    })
  }

  const onImgPick = async (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const f =
      e.target.files?.[0]

    if (!f || !handle) return

    setUploadingImg(true)

    try {
      const { signed_url } =
        await api.upload(f)

      setViewOnce(false)
      setNoSave(false)

      setPending({
        url: signed_url,
        media_type: 'image'
      })
    } catch (err: any) {
      alert(
        err.message ||
          'Could not upload photo'
      )
    }

    setUploadingImg(false)

    if (imgRef.current) {
      imgRef.current.value = ''
    }
  }

  const confirmSendMedia =
    async () => {
      if (!handle || !pending)
        return

      setBusy(true)

      try {
        const m =
          await api.sendDmMedia(
            handle,
            pending.url,
            pending.media_type,
            undefined,
            undefined,
            viewOnce,
            !noSave
          )

        if (!seen.current.has(m.id)) {
          seen.current.add(m.id)

          setMsgs(p => [
            ...p,
            m
          ])
        }

        setPending(null)
        setViewOnce(false)
        setNoSave(false)
      } catch (e: any) {
        alert(
          e.message ||
            'Could not send media'
        )
      }

      setBusy(false)
    }

  const openViewOnce =
    async (id: string) => {
      if (!handle) return

      try {
        const r =
          await api.viewOnceDm(
            handle,
            id
          )

        setViewer({
          url: r.media_url,
          type:
            r.media_type ||
            'image',
          allowSave: false,
          viewOnce: true
        })

        setViewerDragY(0)

        setMsgs(p =>
          p.map(m =>
            m.id === id
              ? {
                  ...m,
                  view_once_viewed:
                    true
                }
              : m
          )
        )
      } catch (e: any) {
        alert(
          e.message ||
            'This media has already been viewed'
        )

        setMsgs(p =>
          p.map(m =>
            m.id === id
              ? {
                  ...m,
                  view_once_viewed:
                    true
                }
              : m
          )
        )
      }
    }

  // Keep the existing Android screenshot
  // protection active while the full-screen
  // viewer is open.
  useEffect(() => {
    if (viewer) {
      secureOn()

      return () => {
        secureOff()
      }
    }
  }, [viewer])

  const callRoom =
    handle && user
      ? `dm-${[
          user.handle,
          handle
        ]
          .sort()
          .join('-')}`
      : ''

  const isSelf =
    !!handle &&
    handle === user?.handle

  const formatDuration = (
    seconds: number
  ) => {
    const s = Math.max(
      0,
      Math.floor(seconds)
    )

    const h = Math.floor(
      s / 3600
    )

    const m = Math.floor(
      (s % 3600) / 60
    )

    const sec = s % 60

    if (h > 0) {
      return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    }

    return `${m}:${String(sec).padStart(2, '0')}`
  }

  const startCall = async (
    media:
      | 'audio'
      | 'video'
  ) => {
    if (
      !handle ||
      isSelf ||
      !callRoom
    ) {
      return
    }

    setCall({
      room: callRoom,
      media
    })

    try {
      await api.callRing(
        handle,
        callRoom,
        media
      )
    } catch (e: any) {
      setCall(null)

      alert(
        e?.message ||
          'Could not start the call'
      )
    }
  }

  const selfThread =
    threads.find(
      t =>
        t.user.handle ===
        user?.handle
    )

  const otherThreads =
    threads.filter(
      t =>
        t.user.handle !==
        user?.handle
    )

  return (
    <div className="flex h-[calc(100dvh-5.25rem-env(safe-area-inset-bottom))] md:h-screen min-h-0 overflow-hidden">

      {call && (
        <CallModal
          room={call.room}
          peer={
            handle &&
            handle !== user?.handle
              ? handle
              : undefined
          }
          media={call.media}
          initiatedByMe={true}
          onClose={() =>
            setCall(null)
          }
          onCallEnded={async (
            duration: number
          ) => {
            const activeCall = call

            setCall(null)

            if (
              !handle ||
              duration < 1
            ) {
              return
            }

            try {
              const m =
                await api.dmSend(
                  handle,
                  `📞 ${
                    activeCall.media ===
                    'video'
                      ? 'Video'
                      : 'Voice'
                  } call · ${formatDuration(
                    duration
                  )}`
                )

              if (
                !seen.current.has(
                  m.id
                )
              ) {
                seen.current.add(
                  m.id
                )

                setMsgs(p => [
                  ...p,
                  m
                ])
              }
            } catch {}
          }}
        />
      )}

      {/* Long-press message action sheet */}

      {messageActions && (
        <div
          className="fixed inset-0 z-[80] bg-black/60 backdrop-blur-sm flex items-end sm:items-center justify-center"
          onClick={() =>
            setMessageActions(null)
          }
        >
          <div
            className="w-full sm:max-w-sm bg-panel border-t sm:border border-edge rounded-t-2xl sm:rounded-2xl p-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)]"
            onClick={e =>
              e.stopPropagation()
            }
          >
            {(() => {
              const selected =
                msgs.find(
                  m =>
                    m.id ===
                    messageActions
                )

              if (!selected)
                return null

              return (
                <>
                  <div className="px-3 py-2 text-xs text-slate-500">
                    Message options
                  </div>

                  {!selected.deleted && (
                    <button
                      type="button"
                      onClick={async () => {
                        await togglePin(
                          selected.id
                        )

                        setMessageActions(
                          null
                        )
                      }}
                      className="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-white/10 text-left"
                    >
                      <span className="h-10 w-10 rounded-xl bg-amber-500/15 grid place-items-center">
                        <Pin className="h-5 w-5 text-amber-400" />
                      </span>

                      <span className="font-medium">
                        {selected.pinned
                          ? 'Unpin message'
                          : 'Pin message'}
                      </span>
                    </button>
                  )}

                  {selected.mine &&
                    !selected.deleted && (
                      <button
                        type="button"
                        onClick={() =>
                          deleteMessage(
                            selected.id
                          )
                        }
                        className="w-full flex items-center gap-3 px-4 py-3 rounded-xl hover:bg-rose-500/10 text-left text-rose-400"
                      >
                        <span className="h-10 w-10 rounded-xl bg-rose-500/15 grid place-items-center">
                          <Trash2 className="h-5 w-5" />
                        </span>

                        <span className="font-medium">
                          Delete message
                        </span>
                      </button>
                    )}

                  <button
                    type="button"
                    onClick={() =>
                      setMessageActions(
                        null
                      )
                    }
                    className="w-full mt-2 py-3 rounded-xl bg-white/5 hover:bg-white/10 font-medium"
                  >
                    Cancel
                  </button>
                </>
              )
            })()}
          </div>
        </div>
      )}

      {/* Send media options */}

      {pending && (
        <div
          className="fixed inset-0 z-[72] bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center"
          onClick={() =>
            !busy &&
            setPending(null)
          }
        >
          <div
            onClick={e =>
              e.stopPropagation()
            }
            className="w-full sm:max-w-md bg-panel border-t sm:border border-edge rounded-t-2xl sm:rounded-2xl p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="font-semibold">
                Send media
              </span>

              <button
                onClick={() =>
                  !busy &&
                  setPending(null)
                }
                className="h-8 w-8 grid place-items-center rounded-lg hover:bg-white/10"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="rounded-xl overflow-hidden bg-black grid place-items-center max-h-64 mb-4">
              <img
                src={pending.url}
                alt="preview"
                className="max-h-64 w-auto object-contain"
              />
            </div>

            {/* One-time view */}

            <button
              type="button"
              onClick={() =>
                setViewOnce(v => !v)
              }
              className={`w-full flex items-center gap-3 p-3 rounded-xl border mb-2 text-left transition ${
                viewOnce
                  ? 'border-orange-500/60 bg-orange-500/10'
                  : 'border-edge bg-white/5 hover:bg-white/10'
              }`}
            >
              <span
                className={`h-9 w-9 grid place-items-center rounded-lg shrink-0 ${
                  viewOnce
                    ? 'bg-orange-500 text-white'
                    : 'bg-white/10 text-slate-300'
                }`}
              >
                <Flame className="h-5 w-5" />
              </span>

              <span className="flex-1 min-w-0">
                <span className="block font-medium">
                  One-time view
                </span>

                <span className="block text-xs text-slate-400">
                  Disappears after they open it once
                </span>
              </span>

              <span
                className={`h-6 w-11 rounded-full p-0.5 transition ${
                  viewOnce
                    ? 'bg-orange-500'
                    : 'bg-white/15'
                }`}
              >
                <span
                  className={`block h-5 w-5 rounded-full bg-white transition ${
                    viewOnce
                      ? 'translate-x-5'
                      : ''
                  }`}
                />
              </span>
            </button>

            {/* Block saving */}

            <button
              type="button"
              onClick={() =>
                !viewOnce &&
                setNoSave(v => !v)
              }
              disabled={viewOnce}
              className={`w-full flex items-center gap-3 p-3 rounded-xl border text-left transition ${
                noSave || viewOnce
                  ? 'border-rose-500/60 bg-rose-500/10'
                  : 'border-edge bg-white/5 hover:bg-white/10'
              } ${
                viewOnce
                  ? 'opacity-70 cursor-not-allowed'
                  : ''
              }`}
            >
              <span
                className={`h-9 w-9 grid place-items-center rounded-lg shrink-0 ${
                  noSave || viewOnce
                    ? 'bg-rose-500 text-white'
                    : 'bg-white/10 text-slate-300'
                }`}
              >
                <Lock className="h-5 w-5" />
              </span>

              <span className="flex-1 min-w-0">
                <span className="block font-medium">
                  Block saving 📵
                </span>

                <span className="block text-xs text-slate-400">
                  {viewOnce
                    ? 'Always on for one-time media'
                    : 'They can’t save or download it'}
                </span>
              </span>

              <span
                className={`h-6 w-11 rounded-full p-0.5 transition ${
                  noSave || viewOnce
                    ? 'bg-rose-500'
                    : 'bg-white/15'
                }`}
              >
                <span
                  className={`block h-5 w-5 rounded-full bg-white transition ${
                    noSave || viewOnce
                      ? 'translate-x-5'
                      : ''
                  }`}
                />
              </span>
            </button>

            <button
              type="button"
              onClick={
                confirmSendMedia
              }
              disabled={busy}
              className="mt-4 w-full py-3 rounded-xl bg-gradient-to-r from-brand to-violet-600 font-semibold flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {busy ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Send className="h-5 w-5" />
              )}

              Send
            </button>
          </div>
        </div>
      )}

      {/* Full-screen photo / media viewer */}

      {viewer && (
        <div
          className="fixed inset-0 z-[70] bg-black flex flex-col overflow-hidden"
          onContextMenu={
            !viewer.allowSave
              ? e =>
                  e.preventDefault()
              : undefined
          }
        >
          {/* Viewer header */}

          <div className="flex items-center justify-between px-4 pt-[env(safe-area-inset-top)] min-h-16 border-b border-white/10 shrink-0">
            <div className="flex items-center gap-2 min-w-0">
              {viewer.viewOnce ? (
                <>
                  <Flame className="h-4 w-4 text-orange-300 shrink-0" />

                  <span className="font-semibold text-orange-300 truncate">
                    One-time view
                  </span>
                </>
              ) : (
                <>
                  <ImageIcon className="h-4 w-4 text-slate-300 shrink-0" />

                  <span className="font-semibold truncate">
                    Photo
                  </span>
                </>
              )}

              {!viewer.allowSave && (
                <span className="flex items-center gap-1 text-[11px] text-rose-300 shrink-0">
                  📵 Saving blocked
                </span>
              )}
            </div>

            {/* Larger close button */}

            <button
              onClick={closeViewer}
              className="h-12 w-12 grid place-items-center rounded-full bg-white/10 hover:bg-white/20 active:bg-white/25 shrink-0"
              title="Close"
              aria-label="Close photo"
            >
              <X className="h-7 w-7" />
            </button>
          </div>

          {/* Swipeable media area */}

          <div
            className={`flex-1 min-h-0 grid place-items-center p-4 touch-none ${
              !viewer.allowSave
                ? 'select-none'
                : ''
            }`}
            onPointerDown={
              onViewerPointerDown
            }
            onPointerMove={
              onViewerPointerMove
            }
            onPointerUp={
              onViewerPointerUp
            }
            onPointerCancel={
              onViewerPointerCancel
            }
            style={{
              transform: `translateY(${viewerDragY}px)`,
              opacity: Math.max(
                0.35,
                1 -
                  viewerDragY /
                    500
              ),
              transition:
                viewerDragging
                  ? 'none'
                  : 'transform 180ms ease, opacity 180ms ease'
            }}
          >
            {viewer.type ===
            'video' ? (
              <video
                src={viewer.url}
                controls
                autoPlay
                className="max-h-full max-w-full rounded-lg"
                controlsList={
                  !viewer.allowSave
                    ? 'nodownload'
                    : undefined
                }
                onContextMenu={
                  !viewer.allowSave
                    ? e =>
                        e.preventDefault()
                    : undefined
                }
              />
            ) : (
              <img
                src={viewer.url}
                alt="Full size photo"
                draggable={
                  viewer.allowSave
                }
                onContextMenu={
                  !viewer.allowSave
                    ? e =>
                        e.preventDefault()
                    : undefined
                }
                className={`max-h-full max-w-full rounded-lg object-contain ${
                  !viewer.allowSave
                    ? 'select-none'
                    : ''
                }`}
              />
            )}
          </div>

          {/* Viewer footer */}

          <div className="text-center text-xs pb-[calc(env(safe-area-inset-bottom)+1rem)] pt-2 px-4 shrink-0">
            {viewer.viewOnce ? (
              <span className="text-slate-500">
                Swipe down or tap ✕ to close. This can only be viewed once.
              </span>
            ) : viewer.allowSave ? (
              <span className="text-slate-500">
                Swipe down or tap ✕ to return to the conversation.
              </span>
            ) : (
              <span className="text-rose-300 flex items-center justify-center gap-1">
                📵 Saving and downloading are blocked. Swipe down or tap ✕ to close.
              </span>
            )}
          </div>
        </div>
      )}

      {/* Threads list */}

      <div
        className={`${
          handle
            ? 'hidden lg:flex'
            : 'flex'
        } flex-col w-full lg:w-80 shrink-0 border-r border-edge`}
      >
        <div className="px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] border-b border-edge font-extrabold text-xl">
          Messages
        </div>

        <button
          onClick={() =>
            nav('/groups')
          }
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 text-left border-b border-edge/60"
        >
          <div className="h-10 w-10 rounded-full bg-white/5 border border-edge grid place-items-center shrink-0">
            <Users className="h-5 w-5 text-brand" />
          </div>

          <div className="min-w-0 flex-1">
            <div className="font-medium truncate">
              Groups
            </div>

            <div className="text-sm text-slate-500 truncate">
              Private Inner-Circle group chats
            </div>
          </div>

          <ChevronRight className="h-4 w-4 text-slate-500" />
        </button>

        <div className="flex-1 overflow-y-auto">
          <button
            onClick={() =>
              nav(
                `/messages/${user?.handle}`
              )
            }
            className={`w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 text-left border-b border-edge/60 ${
              isSelf
                ? 'bg-white/5'
                : ''
            }`}
          >
            <div className="h-10 w-10 rounded-full bg-gradient-to-br from-brand to-violet-600 grid place-items-center shrink-0">
              <Bookmark className="h-5 w-5 text-white" />
            </div>

            <div className="min-w-0 flex-1">
              <div className="font-medium truncate">
                Me, Myself &amp; I
              </div>

              <div className="text-sm text-slate-500 truncate">
                {selfThread
                  ? `${
                      selfThread.mine
                        ? 'You: '
                        : ''
                    }${selfThread.last}`
                  : 'Notes, links & things to remember'}
              </div>
            </div>
          </button>

          {otherThreads.length ===
            0 && (
            <p className="text-slate-500 text-sm p-4">
              No conversations yet. Open someone's profile and start a chat (DMs are tier-gated).
            </p>
          )}

          {otherThreads.map(t => (
            <button
              key={t.user.id}
              onClick={() =>
                nav(
                  `/messages/${t.user.handle}`
                )
              }
              className={`w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 text-left ${
                handle ===
                t.user.handle
                  ? 'bg-white/5'
                  : ''
              }`}
            >
              <Avatar
                id={t.user.id}
                name={
                  t.user.display_name
                }
                url={
                  t.user.avatar_url
                }
              />

              <div className="min-w-0 flex-1">
                <div className="font-medium truncate flex items-center gap-1.5">
                  {t.user.nickname ||
                    t.user.display_name}

                  <RoleBadge
                    role={t.user.role}
                    size={14}
                  />

                  <AccountBadge
                    type={
                      t.user
                        .account_type
                    }
                    role={
                      t.user.role
                    }
                    size={13}
                  />
                </div>

                <div className="text-sm text-slate-500 truncate">
                  {t.mine
                    ? 'You: '
                    : ''}
                  {t.last}
                </div>
              </div>

              {t.unread > 0 && (
                <span className="shrink-0 min-w-[20px] h-5 px-1.5 rounded-full bg-rose-500 text-white text-xs grid place-items-center font-bold">
                  {t.unread > 99
                    ? '99+'
                    : t.unread}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Thread */}

      <div
        className={`${
          handle
            ? 'flex'
            : 'hidden lg:flex'
        } flex-col flex-1 min-w-0 min-h-0 overflow-hidden`}
      >
        {!handle ? (
          <div className="flex-1 grid place-items-center text-slate-500">
            Select a conversation
          </div>
        ) : loading ? (
          <div className="flex-1 grid place-items-center">
            <Loader2 className="h-6 w-6 animate-spin text-slate-500" />
          </div>
        ) : (
          thread && (
            <>
              {/* DM header */}

              <div className="min-h-16 shrink-0 border-b border-edge px-4 pt-[env(safe-area-inset-top)] flex items-center gap-3">
                <button
                  onClick={() =>
                    nav('/messages')
                  }
                  className="lg:hidden"
                >
                  <ArrowLeft className="h-5 w-5" />
                </button>

                {isSelf ? (
                  <div className="h-[38px] w-[38px] rounded-full bg-gradient-to-br from-brand to-violet-600 grid place-items-center shrink-0">
                    <Bookmark className="h-5 w-5 text-white" />
                  </div>
                ) : (
                  <Avatar
                    id={
                      thread.peer.id
                    }
                    name={
                      thread.peer
                        .display_name
                    }
                    url={
                      thread.peer
                        .avatar_url
                    }
                    size={38}
                  />
                )}

                <div
                  className={`flex-1 min-w-0 ${isSelf ? '' : 'cursor-pointer'}`}
                  onClick={() => {
                    if (!isSelf && handle) {
                      nav(`/messages/${handle}/info`)
                    }
                  }}
                >
                  <div className="font-semibold truncate flex items-center gap-1.5">
                    {isSelf
                      ? 'Me, Myself & I'
                      : thread.peer
                          .nickname ||
                        thread.peer
                          .display_name}

                    {!isSelf && (
                      <RoleBadge
                        role={
                          thread.peer
                            .role
                        }
                        size={15}
                      />
                    )}

                    {!isSelf && (
                      <AccountBadge
                        type={
                          thread.peer
                            .account_type
                        }
                        role={
                          thread.peer
                            .role
                        }
                        size={14}
                      />
                    )}

                    {!isSelf &&
                      thread.peer_is_inner && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            editNickname()
                          }}
                          title="Set a private nickname"
                          className="text-slate-500 hover:text-brand ml-0.5"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                      )}
                  </div>

                  <div className="text-xs text-slate-500 truncate">
                    {isSelf
                      ? 'Your private space · only you can see this'
                      : thread.peer
                          .nickname
                        ? `@${thread.peer.handle}`
                        : `#${thread.peer.handle}`}
                  </div>
                </div>

                {!isSelf &&
                  (thread.can_call ? (
                    <>
                      <button
                        onClick={() =>
                          startCall(
                            'audio'
                          )
                        }
                        title="Voice call"
                        className="h-9 w-9 grid place-items-center rounded-lg hover:bg-white/10"
                      >
                        <Phone className="h-4 w-4" />
                      </button>

                      <button
                        onClick={() =>
                          startCall(
                            'video'
                          )
                        }
                        title="Video call"
                        className="h-9 w-9 grid place-items-center rounded-lg hover:bg-white/10"
                      >
                        <Video className="h-4 w-4" />
                      </button>
                    </>
                  ) : (
                    <div
                      title="This person has turned off calls from you"
                      className="flex items-center gap-1 text-slate-600"
                    >
                      <span className="h-9 w-9 grid place-items-center opacity-40 cursor-not-allowed">
                        <Phone className="h-4 w-4" />
                      </span>

                      <span className="h-9 w-9 grid place-items-center opacity-40 cursor-not-allowed">
                        <Video className="h-4 w-4" />
                      </span>
                    </div>
                  ))}
              </div>

              {/* Messages */}

              <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-2">
                {msgs.some(
                  m =>
                    m.pinned &&
                    !m.deleted
                ) && (
                  <div className="sticky top-0 z-10 bg-amber-500/10 border border-amber-500/30 rounded-xl px-3 py-2 text-xs text-amber-200 flex items-center gap-2">
                    <Pin className="h-3.5 w-3.5" />

                    {
                      msgs.filter(
                        m =>
                          m.pinned &&
                          !m.deleted
                      ).length
                    } pinned message(s)
                  </div>
                )}

                {isSelf &&
                  msgs.length ===
                    0 && (
                    <div className="text-center text-slate-500 py-10 px-6">
                      <Bookmark className="h-8 w-8 mx-auto mb-3 text-brand" />

                      <div className="font-medium text-slate-300">
                        Me, Myself &amp; I
                      </div>

                      <p className="text-sm mt-1">
                        Your own private, encrypted space. Jot notes, save links, or drop reminders — only you can see them.
                      </p>
                    </div>
                  )}

                {msgs.map(m => (
                  <div
                    key={m.id}
                    id={`msg-${m.id}`}
                    className={`group flex items-center gap-2 rounded-xl transition-colors duration-500 ${
                      flashId === m.id
                        ? 'bg-brand/15 ring-1 ring-brand/40'
                        : ''
                    } ${
                      m.mine
                        ? 'justify-end'
                        : ''
                    }`}
                    onPointerDown={e => {
                      if (!m.deleted) {
                        startLongPress(
                          m.id,
                          e
                        )
                      }
                    }}
                    onPointerMove={
                      handleMessagePointerMove
                    }
                    onPointerUp={
                      cancelLongPress
                    }
                    onPointerCancel={
                      cancelLongPress
                    }
                    onPointerLeave={
                      cancelLongPress
                    }
                    onContextMenu={e => {
                      e.preventDefault()

                      if (!m.deleted) {
                        setMessageActions(
                          m.id
                        )
                      }
                    }}
                  >
                    {/* Desktop delete control */}

                    {m.mine &&
                      !m.deleted && (
                        <button
                          onClick={() =>
                            deleteMessage(
                              m.id
                            )
                          }
                          className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 transition"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}

                    {/* Desktop pin control */}

                    {!m.deleted && (
                      <button
                        onClick={() =>
                          togglePin(
                            m.id
                          )
                        }
                        title={
                          m.pinned
                            ? 'Unpin'
                            : 'Pin'
                        }
                        className={`opacity-0 group-hover:opacity-100 transition ${
                          m.pinned
                            ? 'text-amber-400 opacity-100'
                            : 'text-slate-500 hover:text-amber-400'
                        }`}
                      >
                        <Pin className="h-3.5 w-3.5" />
                      </button>
                    )}

                    <div
                      className={`max-w-[75%] ${
                        !m.deleted &&
                        m.media_type ===
                          'sticker' &&
                        m.media_url
                          ? ''
                          : `rounded-2xl px-4 py-2 ${
                              m.deleted
                                ? 'bg-white/5 border border-edge text-slate-500 italic'
                                : m.mine
                                  ? 'bg-gradient-to-br from-brand to-violet-600 text-white rounded-br-sm'
                                  : 'bg-white/5 border border-edge rounded-bl-sm'
                            }`
                      }`}
                    >
                      {m.pinned &&
                        !m.deleted && (
                          <Pin className="h-3 w-3 inline mr-1 opacity-70" />
                        )}

                      {m.deleted ? (
                        m.text
                      ) : m.media_type ===
                          'sticker' &&
                        m.media_url ? (
                        <img
                          src={m.media_url}
                          className="max-h-36 w-auto object-contain drop-shadow"
                          draggable={false}
                        />
                      ) : m.view_once ? (
                        m.mine ? (
                          <span className="flex items-center gap-1.5 text-sm opacity-90">
                            <Flame className="h-4 w-4" />

                            {m.view_once_viewed
                              ? 'Opened'
                              : 'One-time photo · sent'}
                          </span>
                        ) : m.view_once_viewed ? (
                          <span className="flex items-center gap-1.5 text-sm text-slate-400">
                            <Flame className="h-4 w-4" />
                            Opened · expired
                          </span>
                        ) : (
                          <button
                            onClick={() =>
                              openViewOnce(
                                m.id
                              )
                            }
                            className="flex items-center gap-1.5 text-sm font-medium"
                          >
                            <Eye className="h-4 w-4" />
                            Tap to view once
                          </button>
                        )
                      ) : m.media_type ===
                          'audio' &&
                        m.media_url ? (
                        <audio
                          src={
                            m.media_url
                          }
                          controls
                          className="max-w-[220px] h-9"
                        />
                      ) : m.media_url ? (
                        <button
                          type="button"
                          onClick={() =>
                            openMediaViewer(
                              m.media_url,
                              m.media_type ||
                                'image',
                              m.allow_save !==
                                false
                            )
                          }
                          onContextMenu={
                            m.allow_save ===
                            false
                              ? e =>
                                  e.preventDefault()
                              : undefined
                          }
                          className="block rounded-lg overflow-hidden text-left cursor-zoom-in"
                          title="Open photo"
                        >
                          <img
                            src={
                              m.media_url
                            }
                            alt="Photo"
                            draggable={
                              m.allow_save !==
                              false
                            }
                            onContextMenu={
                              m.allow_save ===
                              false
                                ? e =>
                                    e.preventDefault()
                                : undefined
                            }
                            className={`rounded-lg max-h-64 w-auto object-contain ${
                              m.allow_save ===
                              false
                                ? 'select-none'
                                : ''
                            }`}
                          />
                        </button>
                      ) : (
                        <Linkify
                          text={
                            m.text
                          }
                        />
                      )}
                    </div>

                    {/* Saving blocked indicator */}

                    {m.allow_save ===
                      false &&
                      m.media_url &&
                      !m.mine && (
                        <div className="flex items-center gap-1 text-[10px] text-rose-300 mt-0.5">
                          <span>📵</span>
                          Saving blocked
                        </div>
                      )}
                  </div>
                ))}

                <div ref={endRef} />
              </div>

              {/* Composer */}

              {thread.can_dm ? (
                <div className="border-t border-edge relative">
                  {/* Sticker panel */}

                  {stickerOpen && (
                    <div className="absolute bottom-full left-0 right-0 bg-panel2 border-t border-edge p-3 max-h-72 overflow-y-auto">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">
                          Your stickers
                        </span>

                        <button
                          onClick={() =>
                            stickerRef.current?.click()
                          }
                          disabled={
                            uploadingSticker
                          }
                          className="text-xs flex items-center gap-1 px-2 py-1 rounded-lg bg-brand/20 text-brand hover:bg-brand/30 disabled:opacity-50"
                        >
                          {uploadingSticker ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Plus className="h-3.5 w-3.5" />
                          )}

                          Add
                        </button>
                      </div>

                      {stickers.length ===
                      0 ? (
                        <p className="text-center text-slate-500 text-sm py-6">
                          No stickers yet. Tap “Add” to upload an image from your phone.
                        </p>
                      ) : (
                        <div className="grid grid-cols-4 gap-2">
                          {stickers.map(
                            s => (
                              <div
                                key={
                                  s.id
                                }
                                className="relative group"
                              >
                                <img
                                  src={
                                    s.url
                                  }
                                  onClick={() =>
                                    sendSticker(
                                      s.url
                                    )
                                  }
                                  className="rounded-lg cursor-pointer h-20 w-full object-contain bg-white/5 hover:ring-2 ring-brand p-1"
                                />

                                <button
                                  onClick={() =>
                                    removeSticker(
                                      s.id
                                    )
                                  }
                                  className="absolute -top-1.5 -right-1.5 h-5 w-5 grid place-items-center rounded-full bg-rose-600 text-white opacity-0 group-hover:opacity-100 transition"
                                >
                                  <X className="h-3 w-3" />
                                </button>
                              </div>
                            )
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* GIF panel */}

                  {gifOpen && (
                    <div className="absolute bottom-full left-0 right-0 bg-panel2 border-t border-edge p-3 max-h-72 overflow-y-auto">
                      <input
                        autoFocus
                        value={gifQ}
                        onChange={e =>
                          searchGifs(
                            e.target.value
                          )
                        }
                        placeholder="Search GIFs (powered by GIPHY)…"
                        className="w-full bg-ink border border-edge rounded-xl px-3 py-2 text-sm outline-none focus:border-brand mb-2"
                      />

                      <div className="grid grid-cols-3 gap-2">
                        {gifs.map(
                          g => (
                            <img
                              key={
                                g.id
                              }
                              src={
                                g.preview
                              }
                              onClick={() =>
                                sendGif(
                                  g.url
                                )
                              }
                              className="rounded-lg cursor-pointer h-24 w-full object-cover hover:ring-2 ring-brand"
                            />
                          )
                        )}
                      </div>
                    </div>
                  )}

                  {/* Composer */}

                  <form
                    onSubmit={send}
                    onDrop={
                      onComposerDrop
                    }
                    onDragOver={e =>
                      e.preventDefault()
                    }
                    className="p-2 flex items-center gap-2"
                  >
                    <input
                      ref={imgRef}
                      type="file"
                      accept="image/*"
                      hidden
                      onChange={
                        onImgPick
                      }
                    />

                    <input
                      ref={stickerRef}
                      type="file"
                      accept="image/*"
                      hidden
                      onChange={
                        onStickerUpload
                      }
                    />

                    <div className="flex-1 min-w-0 h-12 rounded-full border border-edge bg-ink flex items-center px-2 gap-1">
                      <button
                        type="button"
                        onClick={() => {
                          setStickerOpen(
                            o => !o
                          )
                          setGifOpen(
                            false
                          )
                        }}
                        title="Stickers"
                        className={`h-9 w-9 grid place-items-center rounded-full shrink-0 transition ${
                          stickerOpen
                            ? 'bg-brand text-white'
                            : 'text-slate-300 hover:bg-white/10'
                        }`}
                      >
                        <Smile className="h-5 w-5" />
                      </button>

                      <input
                        value={text}
                        onChange={e =>
                          setText(
                            e.target
                              .value
                          )
                        }
                        onPaste={
                          onComposerPaste
                        }
                        placeholder={
                          recording
                            ? 'Recording…'
                            : 'Message...'
                        }
                        disabled={
                          recording
                        }
                        className="flex-1 min-w-0 bg-transparent border-0 outline-none px-1 text-base text-slate-100 placeholder:text-slate-500 disabled:opacity-60"
                      />

                      <button
                        type="button"
                        onClick={
                          openGif
                        }
                        title="GIFs"
                        className={`h-9 px-2 grid place-items-center rounded-full text-[11px] font-bold shrink-0 transition ${
                          gifOpen
                            ? 'bg-brand text-white'
                            : 'text-slate-300 hover:bg-white/10'
                        }`}
                      >
                        GIF
                      </button>

                      <button
                        type="button"
                        onClick={() =>
                          imgRef.current?.click()
                        }
                        disabled={
                          uploadingImg
                        }
                        title="Attach media"
                        className="h-9 w-9 grid place-items-center rounded-full text-slate-300 hover:bg-white/10 shrink-0 disabled:opacity-50"
                      >
                        {uploadingImg ? (
                          <Loader2 className="h-5 w-5 animate-spin" />
                        ) : (
                          <ImageIcon className="h-5 w-5" />
                        )}
                      </button>

                      <button
                        type="button"
                        onClick={() =>
                          imgRef.current?.click()
                        }
                        disabled={
                          uploadingImg
                        }
                        title="Camera / photo"
                        className="h-9 w-9 grid place-items-center rounded-full text-slate-300 hover:bg-white/10 shrink-0 disabled:opacity-50"
                      >
                        <Camera className="h-5 w-5" />
                      </button>
                    </div>

                    <button
                      type={
                        text.trim()
                          ? 'submit'
                          : 'button'
                      }
                      onClick={
                        !text.trim()
                          ? recording
                            ? stopRec
                            : startRec
                          : undefined
                      }
                      disabled={
                        busy ||
                        (!text.trim() &&
                          !(
                            isSelf ||
                            thread.can_voice
                          ))
                      }
                      title={
                        text.trim()
                          ? 'Send message'
                          : recording
                            ? 'Stop recording'
                            : 'Record a voice message'
                      }
                      className={`h-12 w-12 rounded-full grid place-items-center shrink-0 text-white transition shadow-[0_0_18px_rgba(139,92,246,0.30)] ${
                        recording
                          ? 'bg-rose-600 animate-pulse'
                          : 'bg-gradient-to-br from-brand to-violet-600 hover:brightness-110'
                      } disabled:opacity-40 disabled:cursor-not-allowed`}
                    >
                      {busy ? (
                        <Loader2 className="h-5 w-5 animate-spin" />
                      ) : recording ? (
                        <Square className="h-4 w-4" />
                      ) : text.trim() ? (
                        <Send className="h-5 w-5" />
                      ) : (
                        <Mic className="h-5 w-5" />
                      )}
                    </button>
                  </form>
                </div>
              ) : (
                <div className="p-4 border-t border-edge text-center text-sm text-slate-500">
                  You can't DM this person. DMs open only for your Inner Circle or Followers who allow it.
                </div>
              )}
            </>
          )
        )}
      </div>
    </div>
  )
}

import {
  createBrowserEnvelope,
  decodeServerEnvelope,
  DIRECT_MACHINE_ID,
  parseEnvelope,
  type BrowserMessageType,
  type BrowserPayloadMap,
  type Envelope,
  type Ulid,
} from './protocol'
import { useHarnessStore, type HarnessStoreState } from './store'

const INITIAL_RECONNECT_DELAY_MS = 250
const MAX_RECONNECT_DELAY_MS = 4_000

export const SNAPSHOT_RESYNC_CLOSE_CODE = 1013
export const SNAPSHOT_RESYNC_REASON = 'snapshot resync required'

export function webSocketUrl(
  location: Pick<Location, 'host' | 'protocol'> = globalThis.location,
): string {
  const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${scheme}//${location.host}/ws`
}

function selectedRuntime(state: HarnessStoreState) {
  return state.selectedThreadId === null
    ? null
    : (state.threads[state.selectedThreadId] ?? null)
}

/** Own the one direct browser-to-daemon WebSocket and its snapshot barrier. */
export class HarnessSocketClient {
  private socket: WebSocket | null = null
  private reconnectTimer: ReturnType<typeof globalThis.setTimeout> | null = null
  private reconnectAttempt = 0
  private intentionallyClosed = true
  private generation = 0
  private snapshotBarrierThreadId: string | null = null

  connect(): void {
    this.intentionallyClosed = false
    if (
      this.socket !== null &&
      (this.socket.readyState === WebSocket.CONNECTING ||
        this.socket.readyState === WebSocket.OPEN)
    ) {
      return
    }
    if (this.reconnectTimer !== null) {
      globalThis.clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.openSocket(this.reconnectAttempt > 0)
  }

  disconnect(): void {
    this.intentionallyClosed = true
    this.generation += 1
    this.snapshotBarrierThreadId = null
    if (this.reconnectTimer !== null) {
      globalThis.clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    const socket = this.socket
    this.socket = null
    if (
      socket !== null &&
      (socket.readyState === WebSocket.CONNECTING ||
        socket.readyState === WebSocket.OPEN)
    ) {
      socket.close(1000, 'client closed')
    }
    useHarnessStore.getState().setConnection('disconnected')
  }

  createThread(): string {
    const threadId = useHarnessStore.getState().createThread()
    this.requestSnapshot(threadId)
    return threadId
  }

  selectThread(threadId: string): void {
    useHarnessStore.getState().selectThread(threadId)
    this.requestSnapshot(threadId)
  }

  requestSnapshot(threadId?: string): Ulid | null {
    const state = useHarnessStore.getState()
    const selectedThreadId = threadId ?? state.selectedThreadId
    if (selectedThreadId === null) {
      return null
    }
    if (!state.catalog.some((entry) => entry.thread_id === selectedThreadId)) {
      throw new RangeError('thread is not in the local catalog')
    }

    state.markSnapshotPending(selectedThreadId)
    this.snapshotBarrierThreadId = selectedThreadId
    if (!this.isOpen()) {
      this.connect()
      return null
    }
    return this.send('thread.snapshot', { request: true }, selectedThreadId).id
  }

  submitPrompt(prompt: string): Ulid {
    if (!prompt.trim()) {
      throw new TypeError('prompt must not be blank')
    }
    const state = useHarnessStore.getState()
    const threadId = state.selectedThreadId
    if (threadId === null) {
      throw new Error('create or select a thread before submitting a prompt')
    }
    if (selectedRuntime(state)?.awaitingSnapshot) {
      throw new Error('wait for the authoritative thread snapshot before submitting')
    }
    const envelope = this.send('prompt.submit', { prompt }, threadId)
    useHarnessStore.getState().beginPrompt(threadId, envelope.id, prompt)
    return envelope.id
  }

  cancelRun(runId?: Ulid): Ulid {
    const state = useHarnessStore.getState()
    const threadId = state.selectedThreadId
    const activeRun = selectedRuntime(state)?.activeRun
    const selectedRunId = runId ?? activeRun?.run_id
    if (threadId === null || selectedRunId === undefined) {
      throw new Error('there is no active run to cancel')
    }
    const envelope = this.send(
      'run.cancel',
      { run_id: selectedRunId },
      threadId,
    )
    useHarnessStore.getState().markCancelling(threadId, selectedRunId)
    return envelope.id
  }

  private openSocket(reconnecting: boolean): void {
    const generation = ++this.generation
    useHarnessStore
      .getState()
      .setConnection(reconnecting ? 'reconnecting' : 'connecting')

    let socket: WebSocket
    try {
      socket = new WebSocket(webSocketUrl())
    } catch (error) {
      useHarnessStore
        .getState()
        .setTransportError(
          error instanceof Error ? error.message : 'Unable to open Harness socket',
        )
      this.scheduleReconnect()
      return
    }
    this.socket = socket

    socket.addEventListener('open', () => {
      if (generation !== this.generation || socket !== this.socket) {
        socket.close(1000, 'superseded')
        return
      }
      this.reconnectAttempt = 0
      useHarnessStore.getState().setConnection('connected')
      const threadId = useHarnessStore.getState().selectedThreadId
      if (threadId !== null) {
        this.requestSnapshot(threadId)
      }
    })

    socket.addEventListener('message', (event) => {
      if (
        generation !== this.generation ||
        socket !== this.socket ||
        typeof event.data !== 'string'
      ) {
        return
      }
      const envelope = parseEnvelope(event.data)
      if (envelope === null) {
        useHarnessStore
          .getState()
          .setTransportError('Received an invalid daemon envelope')
        return
      }

      const store = useHarnessStore.getState()
      store.observeDaemon(envelope.machine_id)
      if (
        this.snapshotBarrierThreadId !== null &&
        envelope.thread_id === this.snapshotBarrierThreadId
      ) {
        const decoded = decodeServerEnvelope(envelope)
        if (decoded?.type !== 'thread.snapshot') {
          return
        }
        if (store.receiveEnvelope(envelope)) {
          this.snapshotBarrierThreadId = null
        }
        return
      }
      store.receiveEnvelope(envelope)
    })

    socket.addEventListener('error', () => {
      if (generation === this.generation && socket === this.socket) {
        useHarnessStore
          .getState()
          .setTransportError('Harness connection interrupted')
      }
    })

    socket.addEventListener('close', () => {
      if (generation !== this.generation || socket !== this.socket) {
        return
      }
      this.socket = null
      if (this.intentionallyClosed) {
        useHarnessStore.getState().setConnection('disconnected')
        return
      }
      useHarnessStore.getState().setConnection('reconnecting')
      this.scheduleReconnect()
    })
  }

  private scheduleReconnect(): void {
    if (this.intentionallyClosed || this.reconnectTimer !== null) {
      return
    }
    const delay = Math.min(
      INITIAL_RECONNECT_DELAY_MS * 2 ** this.reconnectAttempt,
      MAX_RECONNECT_DELAY_MS,
    )
    this.reconnectAttempt += 1
    this.reconnectTimer = globalThis.setTimeout(() => {
      this.reconnectTimer = null
      this.openSocket(true)
    }, delay)
  }

  private isOpen(): boolean {
    return this.socket?.readyState === WebSocket.OPEN
  }

  private send<Type extends BrowserMessageType>(
    type: Type,
    payload: BrowserPayloadMap[Type],
    threadId: string,
  ): Envelope<Type, BrowserPayloadMap[Type]> {
    if (!this.isOpen() || this.socket === null) {
      throw new Error('Harness is not connected')
    }
    const state = useHarnessStore.getState()
    const envelope = createBrowserEnvelope(
      type,
      payload,
      threadId,
      state.daemonMachineId ?? DIRECT_MACHINE_ID,
    )
    this.socket.send(JSON.stringify(envelope))
    return envelope
  }
}

export const harnessClient = new HarnessSocketClient()

import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
  type PointerEvent,
  type ReactNode,
  type SyntheticEvent,
} from 'react'

import type {
  GateCommitPayload,
  GateOpenPayload,
  JsonValue,
  MemoryFeatures,
  RemovalReason,
  ScoredMemoryCard,
} from './protocol'

const LONG_PRESS_MS = 550
const LONG_PRESS_MOVE_TOLERANCE_PX = 10

type FeatureKey = 'sem' | 'kw' | 'time' | 'proj' | 'freq' | 'hist'

const FEATURE_LABELS: readonly { key: FeatureKey; label: string }[] = [
  { key: 'sem', label: 'Semantic' },
  { key: 'kw', label: 'Keyword' },
  { key: 'time', label: 'Recency' },
  { key: 'proj', label: 'Project' },
  { key: 'freq', label: 'Citation' },
  { key: 'hist', label: 'Edit history' },
]

interface MemoryGateProps {
  gate: GateOpenPayload
  connected: boolean
  cancelling: boolean
  serverError: JsonValue | null
  onCommit: (decision: GateCommitPayload) => void
  onStop: () => void
}

function score(value: number): string {
  return value.toFixed(3)
}

function gateRejectionMessage(detail: JsonValue | null): string | null {
  if (
    typeof detail !== 'object' ||
    detail === null ||
    Array.isArray(detail) ||
    detail.code !== 'gate_not_committable'
  ) {
    return null
  }
  return typeof detail.message === 'string' && detail.message.trim()
    ? detail.message
    : 'That decision no longer matches the open gate. Review it and try again.'
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

export function MemoryGate({
  gate,
  connected,
  cancelling,
  serverError,
  onCommit,
  onStop,
}: MemoryGateProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const longPressTimerRef = useRef<number | null>(null)
  const longPressStartRef = useRef<{
    pointerId: number
    memoryId: string
    x: number
    y: number
  } | null>(null)
  const suppressClickRef = useRef<string | null>(null)
  const [removed, setRemoved] = useState<Partial<Record<string, RemovalReason>>>({})
  const [addedBack, setAddedBack] = useState<string[]>([])
  const [modifierFor, setModifierFor] = useState<string | null>(null)
  const [pendingCommit, setPendingCommit] = useState<{
    errorAtSubmit: JsonValue | null
  } | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog === null) {
      return
    }
    if (!dialog.open) {
      dialog.showModal()
    }
    dialog.focus({ preventScroll: true })
    return () => {
      if (dialog.open) {
        dialog.close()
      }
    }
  }, [])

  useEffect(() => {
    return () => {
      if (longPressTimerRef.current !== null) {
        globalThis.clearTimeout(longPressTimerRef.current)
      }
    }
  }, [])

  const rejection = gateRejectionMessage(serverError)
  const commitRejected =
    pendingCommit !== null &&
    serverError !== pendingCommit.errorAtSubmit &&
    rejection !== null
  const submitting = pendingCommit !== null && !commitRejected
  const removedCount = Object.keys(removed).length
  const finalMemoryCount = gate.injected.length - removedCount + addedBack.length
  const blocked = submitting || cancelling || !connected

  function clearLongPress(): void {
    if (longPressTimerRef.current !== null) {
      globalThis.clearTimeout(longPressTimerRef.current)
      longPressTimerRef.current = null
    }
    longPressStartRef.current = null
  }

  function beginLongPress(
    event: PointerEvent<HTMLButtonElement>,
    memoryId: string,
  ): void {
    if (event.pointerType !== 'touch' || blocked) {
      return
    }
    clearLongPress()
    longPressStartRef.current = {
      pointerId: event.pointerId,
      memoryId,
      x: event.clientX,
      y: event.clientY,
    }
    longPressTimerRef.current = globalThis.setTimeout(() => {
      suppressClickRef.current = memoryId
      setModifierFor(memoryId)
      longPressTimerRef.current = null
      longPressStartRef.current = null
    }, LONG_PRESS_MS)
  }

  function moveLongPress(event: PointerEvent<HTMLButtonElement>): void {
    const start = longPressStartRef.current
    if (start === null || start.pointerId !== event.pointerId) {
      return
    }
    if (
      Math.hypot(event.clientX - start.x, event.clientY - start.y) >
      LONG_PRESS_MOVE_TOLERANCE_PX
    ) {
      clearLongPress()
    }
  }

  function toggleDefaultRemoval(
    event: MouseEvent<HTMLButtonElement>,
    memoryId: string,
  ): void {
    if (suppressClickRef.current === memoryId) {
      suppressClickRef.current = null
      event.preventDefault()
      return
    }
    if (event.altKey) {
      setModifierFor(memoryId)
      return
    }
    setModifierFor(null)
    setRemoved((current) => {
      const next = { ...current }
      if (next[memoryId] === undefined) {
        next[memoryId] = 'not_relevant'
      } else {
        delete next[memoryId]
      }
      return next
    })
  }

  function chooseRemoval(memoryId: string, reason: RemovalReason): void {
    setRemoved((current) => ({ ...current, [memoryId]: reason }))
    setModifierFor(null)
  }

  function toggleAddBack(memoryId: string): void {
    setAddedBack((current) =>
      current.includes(memoryId)
        ? current.filter((candidate) => candidate !== memoryId)
        : [...current, memoryId],
    )
  }

  function submitDecision(): void {
    if (blocked) {
      return
    }
    const decision: GateCommitPayload = {
      run_id: gate.run_id,
      injection_id: gate.injection_id,
      removed: gate.injected.flatMap((card) => {
        const reason = removed[card.memory_id]
        return reason === undefined ? [] : [{ memory_id: card.memory_id, reason }]
      }),
      added_back: gate.near_misses
        .filter((card) => addedBack.includes(card.memory_id))
        .map((card) => card.memory_id),
    }
    setPendingCommit({ errorAtSubmit: serverError })
    setLocalError(null)
    try {
      onCommit(decision)
    } catch (error) {
      setPendingCommit(null)
      setLocalError(errorMessage(error, 'The memory decision could not be sent.'))
    }
  }

  function stopRun(): void {
    if (cancelling || !connected) {
      return
    }
    setLocalError(null)
    try {
      onStop()
    } catch (error) {
      setLocalError(errorMessage(error, 'The run could not be stopped.'))
    }
  }

  function keepDialogOpen(event: SyntheticEvent<HTMLDialogElement>): void {
    event.preventDefault()
    if (modifierFor !== null) {
      setModifierFor(null)
    }
  }

  function onDialogKeyDown(event: KeyboardEvent<HTMLDialogElement>): void {
    if (event.key === 'Escape' && modifierFor !== null) {
      event.preventDefault()
      event.stopPropagation()
      setModifierFor(null)
      return
    }
    const target = event.target
    const isContinue =
      target instanceof HTMLElement && target.dataset.testid === 'memory-gate-continue'
    if (event.key === 'Enter' && (target === event.currentTarget || isContinue)) {
      event.preventDefault()
      submitDecision()
    }
  }

  return (
    <dialog
      ref={dialogRef}
      className="memory-gate"
      data-testid="memory-gate"
      aria-labelledby="memory-gate-title"
      aria-describedby="memory-gate-description"
      aria-busy={submitting}
      tabIndex={-1}
      onCancel={keepDialogOpen}
      onKeyDown={onDialogKeyDown}
    >
      <div className="memory-gate__surface">
        <header className="memory-gate__header">
          <div>
            <p className="eyebrow">First-turn memory check</p>
            <h2 id="memory-gate-title">Review what Harness remembers</h2>
            <p id="memory-gate-description">
              The model has not started. Keep, remove, or add memories, then continue.
            </p>
          </div>
          <div className="memory-gate__identity" aria-label="Injection details">
            <span>
              Injection <code>{gate.injection_id}</code>
            </span>
            <span>
              Scorer <code>{gate.scorer_version}</code>
            </span>
            <span>
              Snapshot <time dateTime={gate.snapshot_ts}>{gate.snapshot_ts}</time>
            </span>
          </div>
        </header>

        <div className="memory-gate__content">
          <section className="memory-gate__section" aria-labelledby="injected-memories-title">
            <div className="memory-gate__section-heading">
              <div>
                <p className="eyebrow">Proposed context</p>
                <h3 id="injected-memories-title">Injected memories</h3>
              </div>
              <p>{gate.injected.length} selected</p>
            </div>
            <p className="memory-gate__help">
              Tap × to mark not relevant. Alt+× or press and hold × for wrong / never.
            </p>
            {gate.injected.length === 0 ? (
              <p className="memory-gate__empty">No memories met the injection threshold.</p>
            ) : (
              <div className="memory-grid">
                {gate.injected.map((card) => (
                  <InjectedCard
                    key={card.memory_id}
                    card={card}
                    reason={removed[card.memory_id]}
                    modifierOpen={modifierFor === card.memory_id}
                    disabled={blocked}
                    onRemove={toggleDefaultRemoval}
                    onLongPressStart={beginLongPress}
                    onLongPressMove={moveLongPress}
                    onLongPressEnd={clearLongPress}
                    onChooseReason={chooseRemoval}
                    onCloseModifier={() => setModifierFor(null)}
                  />
                ))}
              </div>
            )}
          </section>

          <section className="memory-gate__section" aria-labelledby="near-misses-title">
            <div className="memory-gate__section-heading">
              <div>
                <p className="eyebrow">Just below the line</p>
                <h3 id="near-misses-title">Near misses</h3>
              </div>
              <p>{addedBack.length} added</p>
            </div>
            {gate.near_misses.length === 0 ? (
              <p className="memory-gate__empty">No near-miss memories were returned.</p>
            ) : (
              <div className="memory-grid">
                {gate.near_misses.map((card) => {
                  const added = addedBack.includes(card.memory_id)
                  return (
                    <MemoryCardFrame
                      key={card.memory_id}
                      card={card}
                      tone={added ? 'added' : 'near-miss'}
                      action={
                        <button
                          className="memory-card__add"
                          type="button"
                          data-testid="near-miss-toggle"
                          data-memory-id={card.memory_id}
                          aria-pressed={added}
                          disabled={blocked}
                          onClick={() => toggleAddBack(card.memory_id)}
                        >
                          {added ? 'Added ✓' : '+ Add'}
                        </button>
                      }
                    />
                  )
                })}
              </div>
            )}
          </section>
        </div>

        <footer className="memory-gate__footer">
          <div className="memory-gate__summary" aria-live="polite">
            <strong>
              {finalMemoryCount} {finalMemoryCount === 1 ? 'memory' : 'memories'} will be used
            </strong>
            <span>{removedCount} removed · {addedBack.length} added</span>
          </div>
          {(localError !== null || commitRejected || !connected) && (
            <p className="memory-gate__error" role="alert">
              {localError ??
                (commitRejected
                  ? rejection
                  : 'Connection lost. Your choices remain; reconnect before continuing.')}
            </p>
          )}
          <div className="memory-gate__actions">
            <button
              className="memory-gate__stop"
              type="button"
              data-testid="memory-gate-stop"
              disabled={cancelling || !connected}
              onClick={stopRun}
            >
              {cancelling ? 'Stopping…' : 'Stop run'}
            </button>
            <button
              className="memory-gate__continue"
              type="button"
              data-testid="memory-gate-continue"
              disabled={blocked}
              onClick={submitDecision}
            >
              {submitting ? 'Applying memory…' : 'Continue'}
              {!submitting && <span aria-hidden="true">↗</span>}
            </button>
          </div>
        </footer>
      </div>
    </dialog>
  )
}

interface InjectedCardProps {
  card: ScoredMemoryCard
  reason: RemovalReason | undefined
  modifierOpen: boolean
  disabled: boolean
  onRemove: (event: MouseEvent<HTMLButtonElement>, memoryId: string) => void
  onLongPressStart: (
    event: PointerEvent<HTMLButtonElement>,
    memoryId: string,
  ) => void
  onLongPressMove: (event: PointerEvent<HTMLButtonElement>) => void
  onLongPressEnd: () => void
  onChooseReason: (memoryId: string, reason: RemovalReason) => void
  onCloseModifier: () => void
}

function InjectedCard({
  card,
  reason,
  modifierOpen,
  disabled,
  onRemove,
  onLongPressStart,
  onLongPressMove,
  onLongPressEnd,
  onChooseReason,
  onCloseModifier,
}: InjectedCardProps) {
  const removed = reason !== undefined
  const removeButtonRef = useRef<HTMLButtonElement>(null)
  const firstReasonRef = useRef<HTMLButtonElement>(null)
  const modifierWasOpenRef = useRef(false)
  const modifierId = `memory-reason-${card.memory_id}`

  useEffect(() => {
    if (modifierOpen && !modifierWasOpenRef.current) {
      firstReasonRef.current?.focus({ preventScroll: true })
    } else if (!modifierOpen && modifierWasOpenRef.current) {
      removeButtonRef.current?.focus({ preventScroll: true })
    }
    modifierWasOpenRef.current = modifierOpen
  }, [modifierOpen])

  return (
    <MemoryCardFrame
      card={card}
      tone={removed ? 'removed' : 'injected'}
      status={removed ? `Removed · ${reason.replace('_', ' ')}` : undefined}
      action={
        <div className="memory-card__decision">
          <button
            ref={removeButtonRef}
            className="memory-card__remove"
            type="button"
            data-testid="memory-remove"
            data-memory-id={card.memory_id}
            aria-pressed={removed}
            aria-haspopup="dialog"
            aria-expanded={modifierOpen}
            aria-controls={modifierOpen ? modifierId : undefined}
            aria-label={
              removed
                ? `Restore ${card.label}`
                : `Remove ${card.label} as not relevant`
            }
            title="Remove as not relevant. Hold Alt or press and hold for wrong / never."
            disabled={disabled}
            onPointerDown={(event) => onLongPressStart(event, card.memory_id)}
            onPointerMove={onLongPressMove}
            onPointerUp={onLongPressEnd}
            onPointerCancel={onLongPressEnd}
            onPointerLeave={onLongPressEnd}
            onContextMenu={(event) => event.preventDefault()}
            onClick={(event) => onRemove(event, card.memory_id)}
          >
            <span aria-hidden="true">×</span>
          </button>
          {modifierOpen && (
            <div
              id={modifierId}
              className="memory-card__modifier"
              role="dialog"
              aria-label={`Why remove ${card.label}?`}
              data-testid="memory-modifier"
            >
              <span>Remove as</span>
              <button
                ref={firstReasonRef}
                type="button"
                disabled={disabled}
                onClick={() => onChooseReason(card.memory_id, 'wrong')}
              >
                Wrong
              </button>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onChooseReason(card.memory_id, 'never')}
              >
                Never
              </button>
              <button type="button" disabled={disabled} onClick={onCloseModifier}>
                Cancel
              </button>
            </div>
          )}
        </div>
      }
    />
  )
}

interface MemoryCardFrameProps {
  card: ScoredMemoryCard
  tone: 'injected' | 'removed' | 'near-miss' | 'added'
  status?: string
  action: ReactNode
}

function MemoryCardFrame({ card, tone, status, action }: MemoryCardFrameProps) {
  return (
    <article
      className={`memory-card memory-card--${tone}`}
      data-testid="memory-card"
      data-memory-id={card.memory_id}
      data-tone={tone}
    >
      <header className="memory-card__header">
        <div className="memory-card__title">
          <div className="memory-card__badges">
            <span>#{card.rank}</span>
            <span>{card.kind.replace('_', ' ')}</span>
            {card.pin && <span className="memory-card__pin">Pinned</span>}
          </div>
          <h4>{card.label}</h4>
          {status !== undefined && <p className="memory-card__status">{status}</p>}
        </div>
        {action}
      </header>
      <p className="memory-card__body">{card.body}</p>
      <div className="memory-card__score">
        <div className="memory-card__total" data-testid="memory-total-score">
          <span>Total score</span>
          <strong>{score(card.score)}</strong>
        </div>
        <FeatureScores features={card.features} />
      </div>
      <code className="memory-card__id">{card.memory_id}</code>
    </article>
  )
}

function FeatureScores({ features }: { features: MemoryFeatures }) {
  return (
    <div className="feature-scores" aria-label="Six raw, unweighted feature scores">
      {FEATURE_LABELS.map(({ key, label }) => {
        const value = features[key]
        return (
          <div
            className="feature-score"
            key={key}
            data-testid="memory-feature"
            data-feature={key}
          >
            <span className="feature-score__label">{label}</span>
            <span className="feature-score__track" aria-hidden="true">
              <span style={{ width: `${Math.min(1, Math.max(0, value)) * 100}%` }} />
            </span>
            <span className="feature-score__value">{score(value)}</span>
          </div>
        )
      })}
      <p>Raw feature scores · unweighted</p>
    </div>
  )
}

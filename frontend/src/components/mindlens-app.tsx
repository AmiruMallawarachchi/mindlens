"use client";

import {
  AlertCircle,
  ArrowUpRight,
  Bell,
  BookOpenText,
  Brain,
  CalendarDays,
  ChartNoAxesCombined,
  Check,
  ChevronDown,
  ChevronRight,
  Circle,
  Copy,
  Database,
  Eye,
  Flame,
  Heart,
  Info,
  LockKeyhole,
  Menu,
  MessageCircleMore,
  Mic,
  MoonStar,
  MoreHorizontal,
  Music2,
  PanelRight,
  Paperclip,
  Play,
  Plus,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  SunMedium,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  TrendingUp,
  Volume2,
  Waves,
  Wind,
  Wrench,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Mood, ShaderAtmosphere } from "./shader-atmosphere";
import { MindLensMark } from "./mindlens-mark";
import { AuthGate } from "./auth-gate";
import { useMindLensClient } from "../lib/use-mindlens-client";
import type { ChatMessage, ConnectionStatus, CrisisResource, EosSnapshot } from "../lib/types";

type View = "chat" | "progress" | "journal" | "memory";
type InspectorTab = "progress" | "music" | "memory";

const MOODS: {
  id: Mood;
  label: string;
  note: string;
  icon: typeof Waves;
}[] = [
  { id: "neutral", label: "Balanced", note: "Clear and focused", icon: Sparkles },
  { id: "calm", label: "Calm", note: "Cool and unhurried", icon: Waves },
  { id: "anxious", label: "Anxious", note: "Soft and grounded", icon: Wind },
  { id: "sad", label: "Low", note: "Warm and gentle", icon: MoonStar },
  { id: "angry", label: "Angry", note: "Ember and steady", icon: Flame },
  { id: "hopeful", label: "Hopeful", note: "Open and bright", icon: SunMedium },
];

// Maps the backend's go-emotions surface_emotion (28-class taxonomy, see
// backend/app/core/emotion_labels.py) onto the six atmosphere moods.
const MOOD_BY_EMOTION: Record<string, Mood> = {
  anger: "angry",
  annoyance: "angry",
  disapproval: "angry",
  disgust: "angry",
  fear: "anxious",
  nervousness: "anxious",
  embarrassment: "anxious",
  sadness: "sad",
  grief: "sad",
  disappointment: "sad",
  remorse: "sad",
  relief: "calm",
  approval: "calm",
  caring: "calm",
  joy: "hopeful",
  amusement: "hopeful",
  excitement: "hopeful",
  gratitude: "hopeful",
  love: "hopeful",
  pride: "hopeful",
  admiration: "hopeful",
  optimism: "hopeful",
  desire: "hopeful",
  curiosity: "hopeful",
  neutral: "neutral",
  confusion: "neutral",
  surprise: "neutral",
  realization: "neutral",
};

function moodFromEmotion(surfaceEmotion: string | undefined): Mood | null {
  if (!surfaceEmotion) return null;
  return MOOD_BY_EMOTION[surfaceEmotion] ?? null;
}

const SESSION_GROUPS = [
  {
    label: "Today",
    sessions: ["Exam pressure and sleep", "A quick morning check-in"],
  },
  {
    label: "Previous 7 days",
    sessions: ["Finding focus again", "A difficult conversation", "Sunday reflection"],
  },
];

const NAV_ITEMS: { id: View; label: string; icon: typeof MessageCircleMore }[] = [
  { id: "chat", label: "Chat", icon: MessageCircleMore },
  { id: "progress", label: "Progress", icon: ChartNoAxesCombined },
  { id: "journal", label: "Journal", icon: BookOpenText },
  { id: "memory", label: "Memory", icon: Brain },
];

function StatusDot({ active = false }: { active?: boolean }) {
  return <span className={`status-dot ${active ? "is-active" : ""}`} />;
}

function Sidebar({
  view,
  setView,
  open,
  close,
  openSettings,
  userName,
  onNewConversation,
}: {
  view: View;
  setView: (view: View) => void;
  open: boolean;
  close: () => void;
  openSettings: () => void;
  userName: string;
  onNewConversation: () => void;
}) {
  const initials = userName
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase() || "?";

  return (
    <>
      <button
        className={`mobile-scrim ${open ? "is-visible" : ""}`}
        aria-label="Close navigation"
        onClick={close}
      />
      <aside className={`sidebar glass-panel ${open ? "is-open" : ""}`}>
        <div className="sidebar-header">
          <MindLensMark />
          <button className="icon-button mobile-only" onClick={close} aria-label="Close navigation">
            <X size={18} />
          </button>
        </div>

        <button
          className="new-chat-button"
          onClick={() => {
            setView("chat");
            onNewConversation();
          }}
        >
          <Plus size={18} />
          New conversation
          <span className="key-hint">⌘ K</span>
        </button>

        <nav className="primary-nav" aria-label="Primary navigation">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={view === item.id ? "is-active" : ""}
                onClick={() => {
                  setView(item.id);
                  close();
                }}
              >
                <Icon size={18} />
                <span>{item.label}</span>
                {item.id === "progress" && <span className="nav-badge">3</span>}
              </button>
            );
          })}
        </nav>

        <div className="session-heading">
          <span>Conversations</span>
          <button aria-label="Search conversations">
            <Search size={15} />
          </button>
        </div>

        <div className="session-list">
          {SESSION_GROUPS.map((group) => (
            <div className="session-group" key={group.label}>
              <small>{group.label}</small>
              {group.sessions.map((session, index) => (
                <button
                  key={session}
                  className={index === 0 && group.label === "Today" ? "is-current" : ""}
                  onClick={() => {
                    setView("chat");
                    close();
                  }}
                >
                  <span>{session}</span>
                  {index === 0 && group.label === "Today" && <StatusDot active />}
                </button>
              ))}
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <button className="profile-card" onClick={openSettings}>
            <span className="avatar">{initials}</span>
            <span>
              <strong>{userName}</strong>
              <small>Personal space</small>
            </span>
            <MoreHorizontal size={17} />
          </button>
        </div>
      </aside>
    </>
  );
}

/** Renders the actual agents/EOS/degradation metadata for one assistant turn
 * — this is real orchestration telemetry, not illustrative content. */
function ActivityPanel({
  expanded,
  setExpanded,
  agentsUsed,
  eos,
  degraded,
}: {
  expanded: boolean;
  setExpanded: (value: boolean) => void;
  agentsUsed: string[];
  eos?: EosSnapshot;
  degraded?: string[];
}) {
  const summary = agentsUsed.length
    ? `${agentsUsed.length} agent${agentsUsed.length > 1 ? "s" : ""} · ${eos?.modality ?? "—"} approach`
    : "Agent activity";

  return (
    <div className={`activity-card ${expanded ? "is-expanded" : ""}`}>
      <button
        className="activity-summary"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <span className="activity-orb">
          <span />
        </span>
        <span className="activity-copy">
          <strong>MindLens activity</strong>
          <small>{summary}</small>
        </span>
        <ChevronDown size={17} />
      </button>

      {expanded && (
        <div className="activity-steps">
          <div className="activity-step">
            <span className="step-icon">
              <ShieldCheck size={15} />
            </span>
            <span>
              <strong>Safety check</strong>
              <small>No crisis indicators detected</small>
            </span>
            <Check size={15} className="step-check" />
          </div>

          {eos && (
            <div className="activity-step">
              <span className="step-icon">
                <Brain size={15} />
              </span>
              <span>
                <strong>Emotional context</strong>
                <small>
                  {eos.surface_emotion ?? "neutral"}
                  {typeof eos.distress_level === "number"
                    ? ` · distress ${eos.distress_level.toFixed(2)}`
                    : ""}
                </small>
              </span>
              <Check size={15} className="step-check" />
            </div>
          )}

          {agentsUsed.length > 0 && (
            <div className="activity-step">
              <span className="step-icon">
                <Wrench size={15} />
              </span>
              <span>
                <strong>Agents engaged</strong>
                <small>{agentsUsed.join(", ")}</small>
              </span>
              <Check size={15} className="step-check" />
            </div>
          )}

          {degraded && degraded.length > 0 && (
            <div className="activity-step is-degraded">
              <span className="step-icon">
                <AlertCircle size={15} />
              </span>
              <span>
                <strong>Degraded response</strong>
                <small>Fell back to a template ({degraded.join(", ")})</small>
              </span>
            </div>
          )}

          <p className="activity-note">
            <Info size={13} />
            This is a useful activity summary—not the model&apos;s private reasoning.
          </p>
        </div>
      )}
    </div>
  );
}

function ChatView({
  activityExpanded,
  setActivityExpanded,
  mood,
  adaptive,
  messages,
  sendMessage,
  thinking,
  activeAgents,
  connectionStatus,
  crisis,
  dismissCrisis,
}: {
  activityExpanded: boolean;
  setActivityExpanded: (value: boolean) => void;
  mood: Mood;
  adaptive: boolean;
  messages: ChatMessage[];
  sendMessage: (text: string) => void;
  thinking: boolean;
  activeAgents: string[];
  connectionStatus: ConnectionStatus;
  crisis: { text: string; resources: CrisisResource[] } | null;
  dismissCrisis: () => void;
}) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const canSend = connectionStatus === "open" && !thinking;

  const submit = () => {
    const clean = draft.trim();
    if (!clean || !canSend) return;
    sendMessage(clean);
    setDraft("");
  };

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, thinking]);

  const latestModality = [...messages]
    .reverse()
    .find((message) => message.role === "assistant" && message.eos?.modality)
    ?.eos?.modality;

  return (
    <div className="chat-view">
      <div className="conversation-header">
        <div>
          <span className="eyebrow">A safe space for what&apos;s real</span>
          <h1>Current conversation</h1>
        </div>
        <div className="conversation-meta">
          {latestModality && (
            <span className="approach-badge">
              <Sparkles size={13} />
              {latestModality} approach
            </span>
          )}
          {connectionStatus !== "open" && (
            <span className="connection-pill" data-status={connectionStatus}>
              <StatusDot active={false} />
              {connectionStatus === "connecting" && "Connecting…"}
              {connectionStatus === "reconnecting" && "Reconnecting…"}
              {connectionStatus === "closed" && "Disconnected"}
              {connectionStatus === "idle" && "Starting session…"}
            </span>
          )}
          <button className="icon-button" aria-label="Conversation options">
            <MoreHorizontal size={18} />
          </button>
        </div>
      </div>

      {crisis && (
        <div className="crisis-banner glass-card" role="alert">
          <div>
            <strong>Please reach out to someone who can help right now</strong>
            <ul>
              {crisis.resources.map((resource) => (
                <li key={resource.name}>
                  {resource.name}: <strong>{resource.number}</strong>
                  {resource.available ? ` · ${resource.available}` : ""}
                </li>
              ))}
            </ul>
          </div>
          <button className="button-secondary" onClick={dismissCrisis}>
            I&apos;ve seen this
          </button>
        </div>
      )}

      <div className="message-stream" aria-live="polite">
        {messages.length === 0 && !thinking && (
          <div className="day-divider">
            <span>Tell MindLens what&apos;s on your mind to begin</span>
          </div>
        )}

        {messages.map((message) => (
          <div className={`message-row is-${message.role}`} key={message.id}>
            {message.role === "assistant" && (
              <div className={`assistant-avatar mood-${mood}`} aria-hidden="true">
                <span />
              </div>
            )}
            <div className="message-column">
              <div
                className={`message-bubble ${message.crisis ? "is-crisis" : ""} ${
                  message.kind === "error" ? "is-error" : ""
                }`}
              >
                {message.text}
              </div>
              {message.role === "assistant" && !message.pending && !message.crisis && (
                <div className="message-actions">
                  <button aria-label="Copy response" onClick={() => navigator.clipboard?.writeText(message.text)}>
                    <Copy size={14} />
                  </button>
                  <button aria-label="Helpful response"><ThumbsUp size={14} /></button>
                  <button aria-label="Unhelpful response"><ThumbsDown size={14} /></button>
                </div>
              )}
              {message.role === "assistant" &&
                !message.pending &&
                message.agentsUsed &&
                message.agentsUsed.length > 0 && (
                  <ActivityPanel
                    expanded={activityExpanded}
                    setExpanded={setActivityExpanded}
                    agentsUsed={message.agentsUsed}
                    eos={message.eos}
                    degraded={message.degraded}
                  />
                )}
            </div>
          </div>
        ))}

        {thinking && (
          <div className="message-row is-assistant">
            <div className={`assistant-avatar mood-${mood}`} aria-hidden="true">
              <span />
            </div>
            <div className="thinking-card">
              <span className="thinking-orb"><span /></span>
              <span>
                <strong>Thinking with you</strong>
                <small>
                  {activeAgents.length > 0
                    ? activeAgents.join(", ")
                    : "Understanding what matters most…"}
                </small>
              </span>
              <span className="thinking-dots"><i /><i /><i /></span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="composer-shell">
        <div className="composer glass-panel">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder={
              connectionStatus === "open"
                ? "Tell MindLens what’s on your mind…"
                : "Connecting to MindLens…"
            }
            aria-label="Message MindLens"
            rows={1}
            maxLength={2000}
          />
          <div className="composer-toolbar">
            <div>
              <button className="icon-button" aria-label="Attach a file">
                <Paperclip size={18} />
              </button>
              <button className="icon-button" aria-label="Use voice input">
                <Mic size={18} />
              </button>
              <button className="composer-mode">
                <Sparkles size={14} />
                {adaptive ? "Adaptive" : "Manual"}
                <ChevronDown size={13} />
              </button>
            </div>
            <button
              className="send-button"
              onClick={submit}
              disabled={!draft.trim() || !canSend}
              aria-label="Send message"
            >
              <Send size={17} />
            </button>
          </div>
        </div>
        <p>MindLens can make mistakes. It is a wellbeing companion, not emergency or medical care.</p>
      </div>
    </div>
  );
}

function ProgressView() {
  const bars = [42, 54, 48, 64, 71, 67, 79];
  return (
    <div className="content-view">
      <div className="page-title">
        <div>
          <span className="eyebrow">Your rhythm, not a score</span>
          <h1>A steadier week is taking shape.</h1>
          <p>Small changes across sleep, mood and reflection—viewed with context.</p>
        </div>
        <button className="button-secondary"><CalendarDays size={16} /> Last 7 days</button>
      </div>

      <div className="metrics-grid">
        <article className="metric-card glass-card">
          <span className="metric-icon"><Heart size={18} /></span>
          <small>Average mood</small>
          <strong>6.8<span>/10</span></strong>
          <em className="trend-up"><TrendingUp size={14} /> 12% steadier</em>
        </article>
        <article className="metric-card glass-card">
          <span className="metric-icon"><MoonStar size={18} /></span>
          <small>Sleep average</small>
          <strong>6h 42m</strong>
          <em>Goal: 7 hours</em>
        </article>
        <article className="metric-card glass-card">
          <span className="metric-icon"><BookOpenText size={18} /></span>
          <small>Reflection streak</small>
          <strong>4 days</strong>
          <em>Personal best: 6</em>
        </article>
      </div>

      <article className="trend-card glass-card">
        <div className="card-heading">
          <div><small>Emotional balance</small><h2>Your mood has felt more manageable</h2></div>
          <span className="positive-pill">Improving gently</span>
        </div>
        <div className="bar-chart" aria-label="Mood balance for the last seven days">
          {bars.map((height, index) => (
            <div key={index}>
              <span style={{ height: `${height}%` }} />
              <small>{["M", "T", "W", "T", "F", "S", "S"][index]}</small>
            </div>
          ))}
        </div>
      </article>

      <div className="insight-grid">
        <article className="insight-card glass-card warm">
          <span className="eyebrow">Pattern noticed</span>
          <h3>Sleep changes the tone of your mornings.</h3>
          <p>On nights above 6½ hours, your morning check-ins were noticeably calmer.</p>
          <button>Explore the pattern <ArrowUpRight size={15} /></button>
        </article>
        <article className="insight-card glass-card">
          <span className="eyebrow">A useful next step</span>
          <h3>Protect tonight before planning tomorrow.</h3>
          <p>A three-minute wind-down could help your study plan feel less overwhelming.</p>
          <button>Start wind-down <Play size={14} /></button>
        </article>
      </div>
    </div>
  );
}

function JournalView() {
  return (
    <div className="content-view">
      <div className="page-title">
        <div>
          <span className="eyebrow">Private reflection</span>
          <h1>Make space for the thought underneath.</h1>
          <p>Write freely, follow a prompt, or turn a conversation into a journal entry.</p>
        </div>
        <button className="button-primary"><Plus size={16} /> New entry</button>
      </div>

      <article className="journal-hero glass-card">
        <div className="journal-orb"><BookOpenText size={25} /></div>
        <span className="eyebrow">A prompt for today</span>
        <h2>What am I assuming will happen—and what evidence do I actually have?</h2>
        <p>Take two minutes. You don&apos;t need to make it sound good.</p>
        <button className="button-primary">Start writing <ChevronRight size={16} /></button>
      </article>

      <div className="section-heading">
        <div><span className="eyebrow">Recent entries</span><h2>Your reflections</h2></div>
        <button>View all</button>
      </div>
      <div className="journal-grid">
        {[
          ["The exam feels bigger than it is", "Today", "I noticed I’m treating one result like it decides everything…"],
          ["What I need from this week", "Yesterday", "Less pressure, more structure. I want to stop negotiating with sleep…"],
          ["After talking with Ravi", "18 Jul", "I’m not as far behind as I thought. The plan feels possible now…"],
        ].map(([title, date, excerpt]) => (
          <article className="journal-card glass-card" key={title}>
            <small>{date}</small>
            <h3>{title}</h3>
            <p>{excerpt}</p>
            <button aria-label={`Open ${title}`}><ArrowUpRight size={16} /></button>
          </article>
        ))}
      </div>
    </div>
  );
}

function MemoryView() {
  return (
    <div className="content-view">
      <div className="page-title">
        <div>
          <span className="eyebrow">Transparent personalization</span>
          <h1>You decide what MindLens remembers.</h1>
          <p>Review, correct or remove anything used to make support feel personal.</p>
        </div>
        <button className="button-secondary"><LockKeyhole size={16} /> Privacy controls</button>
      </div>

      <div className="privacy-banner glass-card">
        <ShieldCheck size={23} />
        <div>
          <strong>Your memory is visible and editable.</strong>
          <p>Nothing below is a diagnosis. These notes only help MindLens maintain continuity.</p>
        </div>
        <button>How memory works</button>
      </div>

      <div className="memory-grid">
        {[
          ["Important people", "Ravi", "Friend · taking the same final exam", Heart],
          ["Current focus", "Final exam", "Next Sunday · study plan in progress", CalendarDays],
          ["Helpful preference", "Direct, practical support", "Gentle honesty over generic reassurance", Sparkles],
          ["Wellbeing goal", "Protect 7 hours of sleep", "Especially during high-pressure weeks", MoonStar],
        ].map(([category, title, detail, Icon]) => (
          <article className="memory-card glass-card" key={String(title)}>
            <span className="memory-icon"><Icon size={18} /></span>
            <small>{String(category)}</small>
            <h3>{String(title)}</h3>
            <p>{String(detail)}</p>
            <div>
              <button><Eye size={14} /> Edit</button>
              <button className="danger-action"><Trash2 size={14} /> Forget</button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function RightInspector({
  open,
  close,
  tab,
  setTab,
}: {
  open: boolean;
  close: () => void;
  tab: InspectorTab;
  setTab: (tab: InspectorTab) => void;
}) {
  return (
    <aside className={`right-inspector glass-panel ${open ? "is-open" : ""}`}>
      <div className="inspector-heading">
        <div>
          <span className="eyebrow">Your space</span>
          <strong>Alongside this conversation</strong>
        </div>
        <button className="icon-button" onClick={close} aria-label="Close details panel">
          <X size={17} />
        </button>
      </div>

      <div className="inspector-tabs" role="tablist">
        {(["progress", "music", "memory"] as InspectorTab[]).map((item) => (
          <button
            role="tab"
            aria-selected={tab === item}
            className={tab === item ? "is-active" : ""}
            key={item}
            onClick={() => setTab(item)}
          >
            {item}
          </button>
        ))}
      </div>

      {tab === "progress" && (
        <div className="inspector-content">
          <article className="mini-mood-card">
            <div>
              <small>Right now</small>
              <strong>Pressure, but receptive</strong>
            </div>
            <span className="mood-score">6.4</span>
            <div className="mood-line" aria-hidden="true">
              {[42, 38, 49, 44, 58, 56, 69, 64].map((value, index) => (
                <i key={index} style={{ height: `${value}%` }} />
              ))}
            </div>
            <p>Confidence is lifting as the next step becomes clearer.</p>
          </article>

          <div className="mini-section">
            <div className="mini-section-heading">
              <strong>Today&apos;s anchors</strong>
              <button><Plus size={14} /></button>
            </div>
            {[
              ["Message Ravi", true],
              ["Choose three priority topics", false],
              ["Start wind-down by 11:00 PM", false],
            ].map(([task, done]) => (
              <button className="task-row" key={String(task)}>
                <span className={done ? "is-done" : ""}>
                  {done ? <Check size={13} /> : <Circle size={13} />}
                </span>
                <span>{String(task)}</span>
              </button>
            ))}
          </div>

          <div className="mini-section">
            <div className="mini-section-heading">
              <strong>Suggested reset</strong>
              <span>3 min</span>
            </div>
            <button className="breathing-card">
              <span className="breathing-visual"><span /></span>
              <span><strong>Slow the noise</strong><small>4–6 breathing</small></span>
              <Play size={15} />
            </button>
          </div>
        </div>
      )}

      {tab === "music" && (
        <div className="inspector-content">
          <article className="music-feature">
            <div className="album-art"><Waves size={28} /></div>
            <small>For focused calm</small>
            <strong>Low Tide, Clear Mind</strong>
            <p>Ambient focus · 32 min</p>
            <div>
              <button className="player-button"><Play size={17} /></button>
              <span className="track-line"><i /></span>
              <Volume2 size={15} />
            </div>
          </article>
          <div className="mini-section">
            <div className="mini-section-heading"><strong>Recent soundscapes</strong><button>See all</button></div>
            {["Rain on quiet glass", "Forest after dusk", "Deep work, soft pulse"].map((track, index) => (
              <button className="track-row" key={track}>
                <span><Music2 size={15} /></span>
                <span><strong>{track}</strong><small>{[18, 24, 36][index]} min</small></span>
                <MoreHorizontal size={15} />
              </button>
            ))}
          </div>
        </div>
      )}

      {tab === "memory" && (
        <div className="inspector-content">
          <div className="memory-readout">
            <ShieldCheck size={21} />
            <strong>Recalled for this response</strong>
            <p>Only two memories helped shape the reply.</p>
          </div>
          {[
            ["Ravi", "Friend · same exam"],
            ["Sleep goal", "7 hours during exam week"],
          ].map(([title, detail]) => (
            <div className="recalled-row" key={title}>
              <Database size={15} />
              <span><strong>{title}</strong><small>{detail}</small></span>
              <button aria-label={`View ${title}`}><ChevronRight size={15} /></button>
            </div>
          ))}
          <button className="full-width-button">Review all memory <ArrowUpRight size={14} /></button>
        </div>
      )}
    </aside>
  );
}

function SettingsDialog({
  open,
  close,
  mood,
  setMood,
  adaptive,
  setAdaptive,
  motionEnabled,
  setMotionEnabled,
  onLogout,
}: {
  open: boolean;
  close: () => void;
  mood: Mood;
  setMood: (mood: Mood) => void;
  adaptive: boolean;
  setAdaptive: (value: boolean) => void;
  motionEnabled: boolean;
  setMotionEnabled: (value: boolean) => void;
  onLogout: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, close]);

  if (!open) return null;

  return (
    <div className="modal-layer" role="presentation">
      <button className="modal-backdrop" onClick={close} aria-label="Close customization" />
      <section
        className="settings-dialog glass-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
      >
        <div className="settings-header">
          <div>
            <span className="eyebrow">Make the space yours</span>
            <h2 id="settings-title">Atmosphere & support</h2>
          </div>
          <button className="icon-button" onClick={close} aria-label="Close settings"><X size={18} /></button>
        </div>

        <div className="settings-scroll">
          <div className="setting-row">
            <div className="setting-icon"><Sparkles size={18} /></div>
            <div>
              <strong>Adaptive atmosphere</strong>
              <p>Let colour and motion respond gently to your check-ins.</p>
            </div>
            <button
              className={`switch ${adaptive ? "is-on" : ""}`}
              role="switch"
              aria-checked={adaptive}
              onClick={() => setAdaptive(!adaptive)}
            >
              <span />
            </button>
          </div>

          <div className="setting-block">
            <div className="setting-label">
              <span>Choose an atmosphere</span>
              <small>{adaptive ? "Adaptive is on · manual choice is still available" : "Manual mode"}</small>
            </div>
            <div className="mood-picker">
              {MOODS.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    className={`mood-option mood-swatch-${item.id} ${mood === item.id ? "is-selected" : ""}`}
                    onClick={() => setMood(item.id)}
                  >
                    <span><Icon size={18} /></span>
                    <strong>{item.label}</strong>
                    <small>{item.note}</small>
                    {mood === item.id && <Check size={15} />}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="setting-row">
            <div className="setting-icon"><Waves size={18} /></div>
            <div>
              <strong>Atmosphere motion</strong>
              <p>Slow shader movement and breathing effects.</p>
            </div>
            <button
              className={`switch ${motionEnabled ? "is-on" : ""}`}
              role="switch"
              aria-checked={motionEnabled}
              onClick={() => setMotionEnabled(!motionEnabled)}
            >
              <span />
            </button>
          </div>

          <div className="preference-grid">
            <button><span><Brain size={17} /></span><strong>Support style</strong><small>Balanced</small><ChevronRight size={15} /></button>
            <button><span><Bell size={17} /></span><strong>Check-ins</strong><small>Gentle · evenings</small><ChevronRight size={15} /></button>
            <button><span><Eye size={17} /></span><strong>Interface</strong><small>Comfortable density</small><ChevronRight size={15} /></button>
            <button><span><LockKeyhole size={17} /></span><strong>Memory</strong><small>Ask before saving</small><ChevronRight size={15} /></button>
          </div>
        </div>

        <div className="settings-footer">
          <p><ShieldCheck size={14} /> Crisis support always uses a stable, high-clarity view.</p>
          <div className="settings-footer-actions">
            <button className="button-secondary" onClick={onLogout}>Log out</button>
            <button className="button-primary" onClick={close}>Save preferences</button>
          </div>
        </div>
      </section>
    </div>
  );
}

export function MindLensApp() {
  const client = useMindLensClient();
  const [view, setView] = useState<View>("chat");
  const [mood, setMood] = useState<Mood>("neutral");
  const [adaptive, setAdaptive] = useState(true);
  const [motionEnabled, setMotionEnabled] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activityExpanded, setActivityExpanded] = useState(true);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("progress");

  const activeMood = useMemo(
    () => MOODS.find((item) => item.id === mood) ?? MOODS[0],
    [mood],
  );

  useEffect(() => {
    setInspectorOpen(window.matchMedia("(min-width: 981px)").matches);
  }, []);

  // Let real backend emotion detection drive the atmosphere when adaptive
  // mode is on, rather than a client-side keyword guess.
  useEffect(() => {
    if (!adaptive) return;
    const mapped = moodFromEmotion(client.liveEos?.surface_emotion);
    if (mapped) setMood(mapped);
  }, [adaptive, client.liveEos]);

  if (client.authStatus !== "ready") {
    return (
      <main className={`mindlens-app mood-${mood}`}>
        <ShaderAtmosphere mood={mood} motionEnabled={motionEnabled} />
        <div className="atmosphere-overlay" aria-hidden="true" />
        <div className="noise-layer" aria-hidden="true" />
        {client.authStatus === "checking" ? (
          <div className="auth-gate">
            <div className="auth-card glass-panel auth-loading">
              <MindLensMark />
              <p>Loading your space…</p>
            </div>
          </div>
        ) : (
          <AuthGate
            busy={client.authBusy}
            error={client.authError}
            onLogin={client.login}
            onRegister={client.register}
          />
        )}
      </main>
    );
  }

  const userName = client.user?.nickname || client.user?.name || "You";

  return (
    <main className={`mindlens-app mood-${mood}`}>
      <ShaderAtmosphere mood={mood} motionEnabled={motionEnabled} />
      <div className="atmosphere-overlay" aria-hidden="true" />
      <div className="noise-layer" aria-hidden="true" />

      <div className="mobile-topbar glass-panel">
        <button className="icon-button" onClick={() => setSidebarOpen(true)} aria-label="Open navigation">
          <Menu size={19} />
        </button>
        <MindLensMark compact />
        <button className="icon-button" onClick={() => setInspectorOpen(!inspectorOpen)} aria-label="Open details">
          <PanelRight size={19} />
        </button>
      </div>

      <Sidebar
        view={view}
        setView={setView}
        open={sidebarOpen}
        close={() => setSidebarOpen(false)}
        openSettings={() => setSettingsOpen(true)}
        userName={userName}
        onNewConversation={client.startNewConversation}
      />

      <section className={`workspace ${inspectorOpen && view === "chat" ? "with-inspector" : ""}`}>
        <header className="workspace-topbar">
          <button className="sidebar-trigger icon-button" onClick={() => setSidebarOpen(true)} aria-label="Open navigation">
            <Menu size={19} />
          </button>
          <div className="presence">
            <StatusDot active={client.connectionStatus === "open"} />
            <span>MindLens is here with you</span>
          </div>
          <div className="topbar-actions">
            <button className="atmosphere-pill" onClick={() => setSettingsOpen(true)}>
              <span className={`mini-swatch mood-swatch-${mood}`} />
              <span>{activeMood.label}</span>
              <small>{adaptive ? "Adaptive" : "Manual"}</small>
              <SlidersHorizontal size={14} />
            </button>
            {view === "chat" && (
              <button
                className={`icon-button desktop-only ${inspectorOpen ? "is-active" : ""}`}
                onClick={() => setInspectorOpen(!inspectorOpen)}
                aria-label={inspectorOpen ? "Close details panel" : "Open details panel"}
              >
                <PanelRight size={18} />
              </button>
            )}
          </div>
        </header>

        <div className="workspace-content">
          {view === "chat" && (
            <ChatView
              activityExpanded={activityExpanded}
              setActivityExpanded={setActivityExpanded}
              mood={mood}
              adaptive={adaptive}
              messages={client.messages}
              sendMessage={client.sendMessage}
              thinking={client.thinking}
              activeAgents={client.activeAgents}
              connectionStatus={client.connectionStatus}
              crisis={client.crisis}
              dismissCrisis={client.dismissCrisis}
            />
          )}
          {view === "progress" && <ProgressView />}
          {view === "journal" && <JournalView />}
          {view === "memory" && <MemoryView />}
        </div>
      </section>

      {view === "chat" && (
        <RightInspector
          open={inspectorOpen}
          close={() => setInspectorOpen(false)}
          tab={inspectorTab}
          setTab={setInspectorTab}
        />
      )}

      <nav className="mobile-bottom-nav glass-panel" aria-label="Mobile navigation">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={view === item.id ? "is-active" : ""}
              onClick={() => setView(item.id)}
            >
              <Icon size={19} />
              <span>{item.label}</span>
            </button>
          );
        })}
        <button onClick={() => setSettingsOpen(true)}>
          <Settings2 size={19} />
          <span>Settings</span>
        </button>
      </nav>

      <SettingsDialog
        open={settingsOpen}
        close={() => setSettingsOpen(false)}
        mood={mood}
        setMood={setMood}
        adaptive={adaptive}
        setAdaptive={setAdaptive}
        motionEnabled={motionEnabled}
        setMotionEnabled={setMotionEnabled}
        onLogout={client.logout}
      />
    </main>
  );
}

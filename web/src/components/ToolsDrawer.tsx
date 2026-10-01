import type {
  CapabilityAnalytics,
  CapabilityRecord,
  DiscoverySource,
  EvaluationReport,
  FailureAnalytics,
  LearningStats,
  LessonRecord,
  PatternRecord,
  RepairStrategyRecord
} from "../types/api";
import { Drawer } from "./Drawer";
import { CapabilityManager, EvaluationPanel, LearningDashboard } from "./Inspector";
import { SystemPanel } from "./SystemInfo";

type ToolsTab = "evaluation" | "learning" | "capabilities" | "system";

type ToolsDrawerProps = {
  tab: ToolsTab;
  onTabChange: (tab: ToolsTab) => void;
  backendOnline: boolean;
  evaluationReport: EvaluationReport | null;
  learningStats: LearningStats | null;
  lessons: LessonRecord[];
  patterns: PatternRecord[];
  repairStrategies: RepairStrategyRecord[];
  failureAnalytics: FailureAnalytics[];
  capabilityAnalytics: CapabilityAnalytics[];
  capabilities: CapabilityRecord[];
  capabilitySources: DiscoverySource[];
  onDiscoverCapabilities: (sourceId?: string) => void;
  onTestCapability: (capabilityId: string) => void;
  onApproveCapability: (capabilityId: string) => void;
  onEnableCapability: (capabilityId: string) => void;
  onDisableCapability: (capabilityId: string) => void;
  onRevalidateLesson: (lessonId: string) => void;
  onDeprecateLesson: (lessonId: string) => void;
  onRevalidatePattern: (patternId: string) => void;
  onDeprecatePattern: (patternId: string) => void;
  onClose: () => void;
};

const TABS: { id: ToolsTab; label: string }[] = [
  { id: "evaluation", label: "Evaluation" },
  { id: "learning", label: "Learning Core" },
  { id: "capabilities", label: "Capabilities" },
  { id: "system", label: "System" }
];

/**
 * Developer and operations panels.
 *
 * Evaluation, the Learning Core, capability management and system information
 * are all useful but secondary. They used to be stacked into the inspector
 * alongside the part you were editing; they now live here, behind one button.
 */
export function ToolsDrawer({
  tab,
  onTabChange,
  backendOnline,
  evaluationReport,
  learningStats,
  lessons,
  patterns,
  repairStrategies,
  failureAnalytics,
  capabilityAnalytics,
  capabilities,
  capabilitySources,
  onDiscoverCapabilities,
  onTestCapability,
  onApproveCapability,
  onEnableCapability,
  onDisableCapability,
  onRevalidateLesson,
  onDeprecateLesson,
  onRevalidatePattern,
  onDeprecatePattern,
  onClose
}: ToolsDrawerProps) {
  return (
    <Drawer title="Tools" side="right" onClose={onClose}>
      <div className="inspector-tabs" role="tablist" aria-label="Tool sections">
        {TABS.map((entry) => (
          <button
            type="button"
            key={entry.id}
            role="tab"
            aria-selected={tab === entry.id}
            className={tab === entry.id ? "inspector-tab active" : "inspector-tab"}
            onClick={() => onTabChange(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </div>

      <div className="drawer-section" role="tabpanel">
        {tab === "evaluation" ? <EvaluationPanel report={evaluationReport} /> : null}

        {tab === "learning" ? (
          <LearningDashboard
            stats={learningStats}
            lessons={lessons}
            patterns={patterns}
            repairStrategies={repairStrategies}
            failures={failureAnalytics}
            capabilityAnalytics={capabilityAnalytics}
            onRevalidateLesson={onRevalidateLesson}
            onDeprecateLesson={onDeprecateLesson}
            onRevalidatePattern={onRevalidatePattern}
            onDeprecatePattern={onDeprecatePattern}
          />
        ) : null}

        {tab === "capabilities" ? (
          <CapabilityManager
            capabilities={capabilities}
            sources={capabilitySources}
            onDiscoverCapabilities={onDiscoverCapabilities}
            onTestCapability={onTestCapability}
            onApproveCapability={onApproveCapability}
            onEnableCapability={onEnableCapability}
            onDisableCapability={onDisableCapability}
          />
        ) : null}

        {tab === "system" ? <SystemPanel backendOnline={backendOnline} /> : null}
      </div>
    </Drawer>
  );
}

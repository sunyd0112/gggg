/**
 * LayoutSplit Component (L1 Layout)
 *
 * Two-column layout with configurable ratio using Compound Components pattern.
 * Content is placed in .Left and .Right slots.
 *
 * Sync Mode (default):
 * - Components are matched across columns and share grid rows
 * - Headlines get full-width rows
 * - Similar components (index diff ≤1) share same grid row with top alignment
 * - Mismatched components use 1:N or N:1 mapping
 *
 * NoSync Mode:
 * - Traditional flex layout with independent column content
 *
 * Usage:
 * ```mdx
 * <LayoutSplit ratio="2:1">
 *   <Left>
 *     <Heading level={2}>Left Content</Heading>
 *     <Text>Description text</Text>
 *   </Left>
 *   <Right>
 *     <Heading level={2}>Right Content</Heading>
 *     <ChartBar data={[...]} />
 *   </Right>
 * </LayoutSplit>
 *
 * <LayoutSplit ratio="1:1" nosync>
 *   <!-- Independent flex columns -->
 * </LayoutSplit>
 * ```
 */

'use client';

import React, { type ReactNode, Children, isValidElement } from 'react';
import type { SplitRatio, ThemeName, VibeLevel } from '@/utils/types';

function nodeToText(node: ReactNode): string {
  if (node === null || node === undefined) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(nodeToText).join('');
  if (!isValidElement(node)) return '';
  return nodeToText((node.props as { children?: ReactNode }).children);
}

function isWhitespaceNode(node: ReactNode): boolean {
  return typeof node === 'string' && !node.trim();
}

function isHeadingLevel2Component(comp: ComponentInfo): boolean {
  if (comp.type === 'h2') return true;
  if (comp.type !== 'Heading') return false;
  const props = comp.element.props as { level?: unknown };
  return props.level === 2;
}

function isLeadTextComponent(comp: ComponentInfo): boolean {
  if (comp.type !== 'Text') return false;
  const props = comp.element.props as { variant?: unknown };
  return props.variant === 'lead';
}

function TimelineStyleHeader({ headline, subtitle }: { headline: string; subtitle?: string | null }): JSX.Element {
  return (
    <div style={{ textAlign: 'left' }}>
      <h1
        className="heading-1"
        style={{
          margin: '1.0rem 1.0rem 0 1.0rem',
          textAlign: 'left',
          fontSize: '4rem',
          fontWeight: 700,
          color: 'var(--theme-text)',
          textWrap: 'wrap',
          width: '100%',
          maxWidth: 'none',
        }}
      >
        {headline}
      </h1>
      {subtitle && (
        <p
          style={{
            margin: '0.5rem 1.0rem 0 1.0rem',
            textAlign: 'left',
            fontSize: '1.5rem',
            fontStyle: 'italic',
            color: 'var(--theme-text-muted)',
          }}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}

// =============================================================================
// Types
// =============================================================================

export interface LayoutSplitProps {
  children: ReactNode;
  /** Column width ratio */
  ratio?: SplitRatio;
  /** Theme override */
  theme?: ThemeName;
  /** Vibe modifier */
  vibe?: VibeLevel;
  /** Disable sync mode - use independent flex columns */
  nosync?: boolean;
  /** Enable mirror layout - left column content aligns right with RTL direction */
  mirrorLeft?: boolean;
}

export interface LayoutSplitSlotProps {
  children: ReactNode;
}

interface ComponentInfo {
  element: React.ReactElement;
  type: string;
  index: number;
  isHeadline: boolean;
}

interface GridRow {
  type: 'headline-full' | 'headline-left' | 'headline-right' | 'matched' | 'left-only' | 'right-only' | 'one-to-many' | 'many-to-one';
  left: ComponentInfo[];
  right: ComponentInfo[];
}

// =============================================================================
// Slot Components (exported for standalone use in MDX)
// =============================================================================

/**
 * Left slot for LayoutSplit
 * Can be used as <Left> or <LayoutSplit.Left>
 */
export function Left({ children }: LayoutSplitSlotProps): JSX.Element {
  return <div className="layout-split-left">{children}</div>;
}
Left.displayName = 'Left';

/**
 * Right slot for LayoutSplit
 * Can be used as <Right> or <LayoutSplit.Right>
 */
export function Right({ children }: LayoutSplitSlotProps): JSX.Element {
  return <div className="layout-split-right">{children}</div>;
}
Right.displayName = 'Right';

// =============================================================================
// Ratio Mapping
// =============================================================================

const ratioClassMap: Record<SplitRatio, string> = {
  '1:1': 'layout-split-1-1',
  '2:1': 'layout-split-2-1',
  '1:2': 'layout-split-1-2',
  '3:1': 'layout-split-3-1',
  '1:3': 'layout-split-1-3',
};

const ratioGridMap: Record<SplitRatio, string> = {
  '1:1': '1fr 1fr',
  '2:1': '2fr 1fr',
  '1:2': '1fr 2fr',
  '3:1': '3fr 1fr',
  '1:3': '1fr 3fr',
};

// =============================================================================
// Helper Functions
// =============================================================================

/** Headline components that should span full width or get their own row */
const HEADLINE_TYPES = ['Heading', 'Title', 'SectionTitle', 'h1', 'h2', 'h3'];

/** Get component type name from element */
function getComponentType(element: React.ReactElement): string {
  const type = element.type;
  if (typeof type === 'string') return type;
  if (typeof type === 'function') {
    return (type as { displayName?: string }).displayName || type.name || 'Unknown';
  }
  return 'Unknown';
}

/** Check if component is a headline type */
function isHeadlineComponent(type: string, props?: Record<string, unknown>): boolean {
  // Check for Text with variant="lead" - treat as headline
  if (type === 'Text' && props?.variant === 'lead') {
    return true;
  }
  return HEADLINE_TYPES.some(h => type.toLowerCase().includes(h.toLowerCase()));
}

/** Extract component info from children */
function extractComponents(children: ReactNode): ComponentInfo[] {
  const components: ComponentInfo[] = [];
  let index = 0;

  Children.forEach(children, (child) => {
    if (isValidElement(child)) {
      const type = getComponentType(child);
      const props = child.props as Record<string, unknown>;
      components.push({
        element: child,
        type,
        index,
        isHeadline: isHeadlineComponent(type, props),
      });
      index++;
    }
  });

  return components;
}

/** Check if a component is a "light" trailing component that should group with previous */
function isTrailingComponent(comp: ComponentInfo): boolean {
  // Plain Text (not lead), Caption, or small components
  if (comp.type === 'Text') {
    return true; // Plain text without variant is trailing
  }
  return false;
}

/** Group trailing components with their preceding "heavy" components */
function groupTrailingComponents(components: ComponentInfo[]): ComponentInfo[][] {
  const groups: ComponentInfo[][] = [];
  let currentGroup: ComponentInfo[] = [];

  for (const comp of components) {
    if (isTrailingComponent(comp) && currentGroup.length > 0) {
      // Add trailing component to current group
      currentGroup.push(comp);
    } else {
      // Start new group if we have a previous group
      if (currentGroup.length > 0) {
        groups.push(currentGroup);
      }
      currentGroup = [comp];
    }
  }

  // Push final group
  if (currentGroup.length > 0) {
    groups.push(currentGroup);
  }

  return groups;
}

/** Build grid rows from left and right components with sync matching */
function buildSyncedGridRows(leftComponents: ComponentInfo[], rightComponents: ComponentInfo[]): GridRow[] {
  const rows: GridRow[] = [];

  // Separate headlines from body content
  const leftHeadlines: ComponentInfo[] = [];
  const leftBody: ComponentInfo[] = [];
  const rightHeadlines: ComponentInfo[] = [];
  const rightBody: ComponentInfo[] = [];

  // Extract headlines (only from beginning of each side)
  let leftHeadlinesDone = false;
  let rightHeadlinesDone = false;

  for (const comp of leftComponents) {
    if (!leftHeadlinesDone && comp.isHeadline) {
      leftHeadlines.push(comp);
    } else {
      leftHeadlinesDone = true;
      leftBody.push(comp);
    }
  }

  for (const comp of rightComponents) {
    if (!rightHeadlinesDone && comp.isHeadline) {
      rightHeadlines.push(comp);
    } else {
      rightHeadlinesDone = true;
      rightBody.push(comp);
    }
  }

  // Process headlines first
  const maxHeadlines = Math.max(leftHeadlines.length, rightHeadlines.length);
  for (let i = 0; i < maxHeadlines; i++) {
    const leftH = leftHeadlines[i];
    const rightH = rightHeadlines[i];

    if (leftH && rightH) {
      rows.push({ type: 'matched', left: [leftH], right: [rightH] });
    } else if (leftH) {
      rows.push({ type: 'headline-left', left: [leftH], right: [] });
    } else if (rightH) {
      rows.push({ type: 'headline-right', left: [], right: [rightH] });
    }
  }

  // Group trailing components before matching
  const leftGroups = groupTrailingComponents(leftBody);
  const rightGroups = groupTrailingComponents(rightBody);

  const leftGroupCount = leftGroups.length;
  const rightGroupCount = rightGroups.length;

  if (leftGroupCount === 0 && rightGroupCount === 0) {
    return rows;
  }

  // Match groups instead of individual components
  if (leftGroupCount === rightGroupCount) {
    for (let i = 0; i < leftGroupCount; i++) {
      rows.push({
        type: leftGroups[i].length > 1 || rightGroups[i].length > 1 ? 'matched' : 'matched',
        left: leftGroups[i],
        right: rightGroups[i]
      });
    }
  } else if (leftGroupCount > rightGroupCount && rightGroupCount > 0) {
    const ratio = leftGroupCount / rightGroupCount;
    let leftIdx = 0;

    for (let rightIdx = 0; rightIdx < rightGroupCount; rightIdx++) {
      const nextBoundary = Math.round((rightIdx + 1) * ratio);
      const leftCombined: ComponentInfo[] = [];

      while (leftIdx < nextBoundary && leftIdx < leftGroupCount) {
        leftCombined.push(...leftGroups[leftIdx]);
        leftIdx++;
      }

      rows.push({
        type: leftCombined.length > 1 ? 'many-to-one' : 'matched',
        left: leftCombined,
        right: rightGroups[rightIdx],
      });
    }

    while (leftIdx < leftGroupCount) {
      rows.push({ type: 'left-only', left: leftGroups[leftIdx], right: [] });
      leftIdx++;
    }
  } else if (rightGroupCount > leftGroupCount && leftGroupCount > 0) {
    const ratio = rightGroupCount / leftGroupCount;
    let rightIdx = 0;

    for (let leftIdx = 0; leftIdx < leftGroupCount; leftIdx++) {
      const nextBoundary = Math.round((leftIdx + 1) * ratio);
      const rightCombined: ComponentInfo[] = [];

      while (rightIdx < nextBoundary && rightIdx < rightGroupCount) {
        rightCombined.push(...rightGroups[rightIdx]);
        rightIdx++;
      }

      rows.push({
        type: rightCombined.length > 1 ? 'one-to-many' : 'matched',
        left: leftGroups[leftIdx],
        right: rightCombined,
      });
    }

    while (rightIdx < rightGroupCount) {
      rows.push({ type: 'right-only', left: [], right: rightGroups[rightIdx] });
      rightIdx++;
    }
  } else if (leftGroupCount > 0) {
    for (const group of leftGroups) {
      rows.push({ type: 'left-only', left: group, right: [] });
    }
  } else {
    for (const group of rightGroups) {
      rows.push({ type: 'right-only', left: [], right: group });
    }
  }

  return rows;
}

// =============================================================================
// Sync Layout Renderer
// =============================================================================

interface SyncLayoutProps {
  rows: GridRow[];
  ratio: SplitRatio;
  theme?: ThemeName;
  vibe?: VibeLevel;
  timelineHeader?: { headline: string; subtitle?: string | null } | null;
  mirrorLeft?: boolean;
}

function SyncLayout({ rows, ratio, theme, vibe, timelineHeader, mirrorLeft = false }: SyncLayoutProps): JSX.Element {
  const gridColumns = ratioGridMap[ratio] || ratioGridMap['1:1'];

  return (
    <div
      className="layout-split layout-split-sync"
      data-layout="split"
      data-sync="true"
      data-ratio={ratio}
      data-theme={theme}
      data-vibe={vibe}
      style={{
        display: 'grid',
        gridTemplateRows: timelineHeader ? 'auto 1fr' : '1fr',
        alignItems: 'stretch',
        gap: 'var(--theme-spacing-gap)',
        paddingTop: timelineHeader ? '40px' : 'var(--theme-spacing-padding)',
        paddingLeft: 'var(--theme-spacing-padding)',
        paddingRight: 'var(--theme-spacing-padding)',
        paddingBottom: 'var(--theme-spacing-padding)',
        height: '100%',
      }}
    >
      {timelineHeader && (
        <div
          style={{
            gridRow: '1',
            marginLeft: 'calc(-1 * (var(--theme-spacing-padding) - 56px))',
            marginRight: 'calc(-1 * (var(--theme-spacing-padding) - 56px))',
          }}
        >
          <TimelineStyleHeader headline={timelineHeader.headline} subtitle={timelineHeader.subtitle} />
        </div>
      )}
      <div
        style={{
          gridRow: timelineHeader ? '2' : '1',
          display: 'grid',
          gridTemplateColumns: gridColumns,
          alignContent: 'center',
          alignItems: 'stretch',
          gap: mirrorLeft ? '6rem' : 'var(--theme-spacing-gap)',
          height: '100%',
          minHeight: 0,
          paddingTop: timelineHeader ? '40px' : '0px',
        }}
      >
        {rows.map((row, rowIndex) => {
          const rowKey = `row-${rowIndex}`;

          // Headline rows (only one side has a headline at this index)
          if (row.type === 'headline-left' || row.type === 'headline-right') {
            const headline = row.left[0] || row.right[0];
            return (
              <div
                key={rowKey}
                className="layout-split-row layout-split-row-headline"
                style={{
                  gridColumn: row.type === 'headline-left' ? '1' : '2',
                  display: 'flex',
                  justifyContent: 'flex-start',
                }}
              >
                {headline.element}
              </div>
            );
          }

          // Left-only row
          if (row.type === 'left-only') {
            return (
              <React.Fragment key={rowKey}>
                <div
                  className="layout-split-cell layout-split-cell-left"
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '1rem',
                    // Mirror layout: align items to right (towards center)
                    alignItems: mirrorLeft ? 'flex-start' : undefined,
                    direction: mirrorLeft ? 'rtl' : undefined,
                  }}
                  data-mirror={mirrorLeft ? 'true' : undefined}
                >
                  {row.left.map((comp, i) => (
                    <div 
                      key={`left-${i}`} 
                      className="layout-split-cell-item"
                    >
                      {comp.element}
                    </div>
                  ))}
                </div>
                <div className="layout-split-cell layout-split-cell-right layout-split-cell-empty" />
              </React.Fragment>
            );
          }

          // Right-only row
          if (row.type === 'right-only') {
            return (
              <React.Fragment key={rowKey}>
                <div className="layout-split-cell layout-split-cell-left layout-split-cell-empty" />
                <div
                  className="layout-split-cell layout-split-cell-right"
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '1rem',
                  }}
                >
                  {row.right.map((comp, i) => (
                    <div key={`right-${i}`} className="layout-split-cell-item">
                      {comp.element}
                    </div>
                  ))}
                </div>
              </React.Fragment>
            );
          }

          // Matched or 1:N / N:1 rows
          return (
            <React.Fragment key={rowKey}>
              <div
                className="layout-split-cell layout-split-cell-left"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1rem',
                  alignSelf: 'stretch',
                  // Mirror layout: align items to right (towards center)
                  alignItems: mirrorLeft ? 'flex-start' : undefined,
                  direction: mirrorLeft ? 'rtl' : undefined,
                }}
                data-mirror={mirrorLeft ? 'true' : undefined}
              >
                {row.left.map((comp, i) => (
                  <div
                    key={`left-${i}`}
                    className="layout-split-cell-item"
                  >
                    {comp.element}
                  </div>
                ))}
              </div>
              <div
                className="layout-split-cell layout-split-cell-right"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1rem',
                  alignSelf: 'stretch',
                }}
              >
                {row.right.map((comp, i) => (
                  <div
                    key={`right-${i}`}
                    className="layout-split-cell-item"
                  >
                    {comp.element}
                  </div>
                ))}
              </div>
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

/**
 * LayoutSplit Component
 *
 * Renders a two-column split layout with configurable ratio.
 * Uses Compound Components pattern for semantic slot assignment.
 *
 * @param children - Must contain Left and Right slots
 * @param ratio - Column width ratio (e.g., "2:1", "1:1")
 * @param theme - Optional theme override
 * @param vibe - Optional vibe modifier
 * @param nosync - Disable sync mode (use traditional flex layout)
 */
export function LayoutSplit({
  children,
  ratio = '1:1',
  theme,
  vibe,
  nosync = false,
  mirrorLeft = false,
}: LayoutSplitProps): JSX.Element {
  // Extract Left and Right slots from children
  let leftSlot: React.ReactElement | null = null;
  let rightSlot: React.ReactElement | null = null;

  Children.forEach(children, (child) => {
    if (!isValidElement(child)) return;

    const displayName = (child.type as { displayName?: string }).displayName;
    const componentType = child.type;

    // Match both standalone (Left/Right) and compound (LayoutSplit.Left/Right) patterns
    if (displayName === 'Left' || displayName === 'LayoutSplit.Left' || componentType === Left) {
      leftSlot = child;
    } else if (displayName === 'Right' || displayName === 'LayoutSplit.Right' || componentType === Right) {
      rightSlot = child;
    }
  });

  // NoSync mode: Use traditional flex layout
  if (nosync) {
    const ratioClass = ratioClassMap[ratio] || ratioClassMap['1:1'];
    return (
      <div
        className={`layout-split layout-split-nosync ${ratioClass}`}
        data-layout="split"
        data-sync="false"
        data-ratio={ratio}
        data-theme={theme}
        data-vibe={vibe}
      >
        {leftSlot}
        {rightSlot}
      </div>
    );
  }

  // Sync mode: Extract and match components
  const leftChildren = (leftSlot as React.ReactElement | null)?.props?.children;
  const rightChildren = (rightSlot as React.ReactElement | null)?.props?.children;

  let leftComponents = extractComponents(leftChildren);
  let rightComponents = extractComponents(rightChildren);

  // LayoutTimeline-style headline/subtitle extraction:
  // If a side begins with <Heading level={2}> and <Text variant="lead">,
  // render them as a single slide header (and remove from column content).
  let timelineHeader: { headline: string; subtitle?: string | null } | null = null;
  const tryExtractHeader = (components: ComponentInfo[]): { header: { headline: string; subtitle?: string | null } | null; rest: ComponentInfo[] } => {
    const meaningful = components.filter((c) => !isWhitespaceNode(c.element));
    const first = meaningful[0];
    if (!first || !isHeadingLevel2Component(first)) return { header: null, rest: components };

    const headline = nodeToText((first.element.props as { children?: ReactNode }).children).trim();
    if (!headline) return { header: null, rest: components };

    const second = meaningful[1];
    let subtitle: string | null = null;
    let removeCount = 1;
    if (second && isLeadTextComponent(second)) {
      const s = nodeToText((second.element.props as { children?: ReactNode }).children).trim();
      if (s) subtitle = s;
      removeCount = 2;
    }

    // Remove the first (and optional second) components by original index.
    const indicesToRemove = new Set<number>([first.index]);
    if (removeCount === 2 && second) indicesToRemove.add(second.index);
    const rest = components.filter((c) => !indicesToRemove.has(c.index));
    return { header: { headline, subtitle }, rest };
  };

  const leftExtracted = tryExtractHeader(leftComponents);
  if (leftExtracted.header) {
    timelineHeader = leftExtracted.header;
    leftComponents = leftExtracted.rest;
  } else {
    const rightExtracted = tryExtractHeader(rightComponents);
    if (rightExtracted.header) {
      timelineHeader = rightExtracted.header;
      rightComponents = rightExtracted.rest;
    }
  }

  // Build synced grid rows
  const rows = buildSyncedGridRows(leftComponents, rightComponents);

  return (
    <SyncLayout
      rows={rows}
      ratio={ratio}
      theme={theme}
      vibe={vibe}
      timelineHeader={timelineHeader}
      mirrorLeft={mirrorLeft}
    />
  );
}

// =============================================================================
// Attach Slot Components
// =============================================================================

LayoutSplit.Left = Left;
LayoutSplit.Right = Right;

// =============================================================================
// Exports
// =============================================================================

export default LayoutSplit;

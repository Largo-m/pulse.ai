import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/recent_project_tree_agent_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_pulsing_dot.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';
import 'package:pulse_ai/shared/ui/mouse_hover_builder.dart';

final class RecentProjectTreeNode extends StatelessWidget {
  const RecentProjectTreeNode({
    super.key,
    required this.project,
    required this.isActive,
    required this.isExpanded,
    required this.agents,
    required this.onSelected,
    required this.onAgentSelected,
    required this.onToggleExpanded,
  });

  final LocalProjectEntity project;
  final bool isActive;
  final bool isExpanded;
  final List<RecentProjectTreeAgentUiModel> agents;
  final VoidCallback onSelected;
  final ValueChanged<String> onAgentSelected;
  final VoidCallback onToggleExpanded;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    final String expandSemantics = isExpanded
        ? OrchestratorStrings.recentProjectCollapseSemantics
        : OrchestratorStrings.recentProjectExpandSemantics;
    final String semanticsLabel = isActive
        ? '${OrchestratorStrings.recentProjectActiveSemantics}: '
              '${project.displayName}'
        : '${OrchestratorStrings.recentProjectSelectSemantics}: '
              '${project.displayName}';

    return Semantics(
      container: true,
      label: semanticsLabel,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          MouseHoverBuilder(
            builder: (BuildContext context, bool isHovered) {
              final Color rowBackground = isHovered || isActive
                  ? PulseColors.surfaceContainerHigh
                  : Colors.transparent;

              return AnimatedContainer(
                duration: const Duration(
                  milliseconds: PulseDimensions.borderTransitionMs,
                ),
                curve: Curves.easeInOut,
                decoration: BoxDecoration(
                  color: rowBackground,
                  borderRadius: BorderRadius.circular(PulseRadii.standbyChip),
                ),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onSelected,
                    borderRadius: BorderRadius.circular(PulseRadii.standbyChip),
                    hoverColor: Colors.white.withValues(
                      alpha: PulseDimensions.inkHoverAlpha,
                    ),
                    child: Padding(
                      padding: PulseInsets.sidebarTreeProjectRow,
                      child: Row(
                        children: <Widget>[
                          Icon(
                            Icons.folder_outlined,
                            size: PulseDimensions.sidebarTreeIconSize,
                            color: isHovered || isActive
                                ? PulseColors.primary
                                : PulseColors.outline,
                          ),
                          const SizedBox(
                            width: PulseDimensions.sidebarTreeRowGap,
                          ),
                          Expanded(
                            child: Text(
                              project.displayName,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: (textTheme.bodyMedium ?? const TextStyle())
                                  .copyWith(
                                    color: PulseColors.onSurface,
                                    fontWeight: FontWeight.w500,
                                  ),
                            ),
                          ),
                          Semantics(
                            button: true,
                            label: expandSemantics,
                            child: IconButton(
                              onPressed: onToggleExpanded,
                              iconSize: PulseDimensions.sidebarTreeChevronSize,
                              padding: EdgeInsets.zero,
                              constraints: const BoxConstraints(
                                minWidth:
                                    PulseDimensions.sidebarTreeChevronSize,
                                minHeight:
                                    PulseDimensions.sidebarTreeChevronSize,
                              ),
                              visualDensity: VisualDensity.compact,
                              icon: Icon(
                                isExpanded
                                    ? Icons.expand_more
                                    : Icons.chevron_right,
                                size: PulseDimensions.sidebarTreeChevronSize,
                                color: PulseColors.outline,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
          if (isExpanded && agents.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(
                left: PulseDimensions.sidebarAgentTreeIndent,
                top: PulseDimensions.sectionGapSm,
              ),
              child: DecoratedBox(
                decoration: const BoxDecoration(
                  border: Border(
                    left: BorderSide(color: PulseColors.outlineVariant),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: agents
                      .map(
                        (RecentProjectTreeAgentUiModel agent) =>
                            _RecentProjectAgentRow(
                              agent: agent,
                              onSelected: () => onAgentSelected(agent.slug),
                            ),
                      )
                      .toList(growable: false),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

final class _RecentProjectAgentRow extends StatelessWidget {
  const _RecentProjectAgentRow({required this.agent, required this.onSelected});

  final RecentProjectTreeAgentUiModel agent;
  final VoidCallback onSelected;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    final String semanticsLabel = agent.isActive
        ? '${OrchestratorStrings.recentProjectActiveSemantics}: '
              '${agent.displayName}'
        : '${OrchestratorStrings.recentProjectAgentSelectSemantics}: '
              '${agent.displayName}';

    return Semantics(
      button: true,
      label: semanticsLabel,
      child: MouseHoverBuilder(
        builder: (BuildContext context, bool isHovered) {
          final Color rowBackground = isHovered || agent.isActive
              ? PulseColors.surfaceContainerHighest
              : Colors.transparent;

          return AnimatedContainer(
            duration: const Duration(
              milliseconds: PulseDimensions.borderTransitionMs,
            ),
            curve: Curves.easeInOut,
            decoration: BoxDecoration(
              color: rowBackground,
              borderRadius: BorderRadius.circular(PulseRadii.standbyChip),
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: onSelected,
                borderRadius: BorderRadius.circular(PulseRadii.standbyChip),
                hoverColor: Colors.white.withValues(
                  alpha: PulseDimensions.inkHoverAlpha,
                ),
                child: Padding(
                  padding: PulseInsets.sidebarTreeAgentRow.copyWith(
                    left: PulseDimensions.sidebarAgentTreeInnerPadding,
                  ),
                  child: Row(
                    children: <Widget>[
                      _AgentStatusDot(
                        isActive: agent.isActive,
                        isRunning: agent.isRunning,
                      ),
                      const SizedBox(width: PulseDimensions.sidebarTreeRowGap),
                      Expanded(
                        child: Text(
                          agent.displayName,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: (textTheme.bodyMedium ?? const TextStyle())
                              .copyWith(
                                color: agent.isActive
                                    ? PulseColors.onSurface
                                    : PulseColors.onSurfaceVariant,
                                fontWeight: agent.isActive
                                    ? FontWeight.w600
                                    : FontWeight.w500,
                              ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

final class _AgentStatusDot extends StatelessWidget {
  const _AgentStatusDot({required this.isActive, required this.isRunning});

  final bool isActive;
  final bool isRunning;

  @override
  Widget build(BuildContext context) {
    final Color dotColor = isActive
        ? PulseColors.tertiary
        : PulseColors.outline;

    final Widget dot = Container(
      width: PulseDimensions.sidebarAgentStatusDotSize,
      height: PulseDimensions.sidebarAgentStatusDotSize,
      decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle),
    );

    if (!isRunning) {
      return dot;
    }

    return const SizedBox(
      width: PulseDimensions.sidebarAgentStatusDotSize,
      height: PulseDimensions.sidebarAgentStatusDotSize,
      child: FittedBox(fit: BoxFit.contain, child: OrchestratorPulsingDot()),
    );
  }
}

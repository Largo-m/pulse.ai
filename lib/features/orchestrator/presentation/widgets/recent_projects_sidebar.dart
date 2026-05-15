import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/recent_project_tree_agent_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/recent_project_tree_node.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/ui/pulse_chrome_icon_button.dart';

final class RecentProjectsSidebar extends StatelessWidget {
  const RecentProjectsSidebar({super.key, required this.onNewProject});

  final VoidCallback onNewProject;

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<RecentProjectsCubit, RecentProjectsState>(
      builder: (BuildContext context, RecentProjectsState state) {
        return SizedBox(
          width: PulseDimensions.orchestratorSidebarWidth,
          child: ColoredBox(
            color: PulseColors.surfaceContainer,
            child: DecoratedBox(
              decoration: const BoxDecoration(
                border: Border(
                  right: BorderSide(color: PulseColors.outlineVariant),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  _RecentProjectsSidebarHeader(onNewProject: onNewProject),
                  Expanded(
                    child: ListView.separated(
                      padding: PulseInsets.sidebarNav,
                      itemCount: state.projects.length,
                      separatorBuilder: (BuildContext context, int index) =>
                          const SizedBox(height: PulseDimensions.sectionGapSm),
                      itemBuilder: (BuildContext context, int index) {
                        final LocalProjectEntity project =
                            state.projects[index];
                        final bool isActive =
                            project.id == state.activeProjectId;
                        final bool isExpanded = state.isProjectExpanded(
                          project.id,
                        );

                        return Padding(
                          padding: PulseInsets.sidebarTreeGroup,
                          child: RecentProjectTreeNode(
                            project: project,
                            isActive: isActive,
                            isExpanded: isExpanded,
                            agents: _agentsForProject(project),
                            onSelected: () {
                              unawaited(
                                context
                                    .read<RecentProjectsCubit>()
                                    .selectProject(project.id),
                              );
                            },
                            onToggleExpanded: () {
                              context
                                  .read<RecentProjectsCubit>()
                                  .toggleProjectExpanded(project.id);
                            },
                          ),
                        );
                      },
                    ),
                  ),
                  const DecoratedBox(
                    decoration: BoxDecoration(
                      border: Border(
                        top: BorderSide(color: PulseColors.outlineVariant),
                      ),
                    ),
                    child: SizedBox(
                      height: PulseDimensions.sidebarHeaderPadding,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  List<RecentProjectTreeAgentUiModel> _agentsForProject(
    LocalProjectEntity project,
  ) {
    return const <RecentProjectTreeAgentUiModel>[];
  }
}

final class _RecentProjectsSidebarHeader extends StatelessWidget {
  const _RecentProjectsSidebarHeader({required this.onNewProject});

  final VoidCallback onNewProject;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;

    return DecoratedBox(
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: PulseColors.outlineVariant)),
      ),
      child: Padding(
        padding: PulseInsets.sidebarHeader,
        child: Row(
          children: <Widget>[
            Expanded(
              child: Text(
                OrchestratorStrings.recentProjectsSectionTitle.toUpperCase(),
                style: (textTheme.labelLarge ?? const TextStyle()).copyWith(
                  color: PulseColors.outline,
                  letterSpacing:
                      PulseDimensions.sidebarSectionTitleLetterSpacing,
                ),
              ),
            ),
            PulseChromeIconButton(
              icon: Icons.add,
              onPressed: onNewProject,
              tooltip: OrchestratorStrings.recentProjectNewButtonTooltip,
              semanticsLabel: OrchestratorStrings.recentProjectNewButtonTooltip,
              iconSize: PulseDimensions.sidebarAddButtonIconSize,
              showBorderOnHover: true,
            ),
          ],
        ),
      ),
    );
  }
}

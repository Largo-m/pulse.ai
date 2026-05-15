import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/app/router/route_paths.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_placeholder_feedback.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_app_top_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_bottom_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_breadcrumb_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_empty_state_body.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/recent_projects_sidebar.dart';
import 'package:pulse_ai/shared/theme/pulse_theme_data.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';

final class OrchestratorPage extends StatelessWidget {
  const OrchestratorPage({super.key});

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = PulseThemeData.build();
    return Theme(
      data: theme,
      child: const ColoredBox(
        color: PulseColors.background,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _OrchestratorChrome(),
            Expanded(child: _OrchestratorMainContent()),
            OrchestratorBottomBar(),
          ],
        ),
      ),
    );
  }
}

final class _OrchestratorChrome extends StatelessWidget {
  const _OrchestratorChrome();

  @override
  Widget build(BuildContext context) {
    return OrchestratorAppTopBar(
      onImportProject: () {
        unawaited(
          Navigator.of(
            context,
          ).pushNamed<void>(RoutePaths.orchestratorImportSelectSource),
        );
      },
      onPlaceholder: () =>
          OrchestratorPlaceholderFeedback.showComingSoon(context),
    );
  }
}

final class _OrchestratorMainContent extends StatelessWidget {
  const _OrchestratorMainContent();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<RecentProjectsCubit, RecentProjectsState>(
      builder: (BuildContext context, RecentProjectsState state) {
        final bool showSidebar = state.projects.isNotEmpty;

        return Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (showSidebar) const RecentProjectsSidebar(),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  OrchestratorBreadcrumbBar(),
                  Expanded(child: _OrchestratorScrollableBody()),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

final class _OrchestratorScrollableBody extends StatelessWidget {
  const _OrchestratorScrollableBody();

  @override
  Widget build(BuildContext context) {
    return OrchestratorEmptyStateBody(
      onPlaceholder: () =>
          OrchestratorPlaceholderFeedback.showComingSoon(context),
    );
  }
}

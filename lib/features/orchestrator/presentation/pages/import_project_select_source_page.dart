import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/app/router/route_paths.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/import_project_feedback.dart';
import 'package:pulse_ai/features/orchestrator/presentation/import_project_flow_outcome_handler.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_placeholder_feedback.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/import_project_select_source_body.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_app_top_bar.dart';
import 'package:pulse_ai/shared/theme/pulse_theme_data.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';

final class ImportProjectSelectSourcePage extends StatelessWidget {
  const ImportProjectSelectSourcePage({super.key});

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = PulseThemeData.build();
    return Theme(
      data: theme,
      child: BlocListener<ImportFlowCubit, ImportFlowState>(
        listenWhen: (ImportFlowState previous, ImportFlowState current) =>
            previous.status != current.status &&
            current.status != ImportFlowStatus.idle &&
            current.status != ImportFlowStatus.loading,
        listener: (BuildContext context, ImportFlowState state) {
          unawaited(
            ImportProjectFlowOutcomeHandler.handle(
              state: state,
              onImportSuccessNavigate: () {
                Navigator.of(context).popUntil(
                  (Route<dynamic> route) =>
                      route.settings.name == RoutePaths.orchestrator,
                );
              },
              refreshRecentProjects: () =>
                  context.read<RecentProjectsCubit>().refresh(),
              showImportFailure: () =>
                  ImportProjectFeedback.showImportFailure(context),
              resetImportFlow: () => context.read<ImportFlowCubit>().reset(),
            ),
          );
        },
        child: ColoredBox(
          color: PulseColors.background,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              OrchestratorAppTopBar(
                isWorkspacesActive: true,
                onWorkspaces: () {
                  Navigator.of(context).popUntil(
                    (Route<dynamic> route) =>
                        route.settings.name == RoutePaths.orchestrator,
                  );
                },
                onImportProject: () =>
                    OrchestratorPlaceholderFeedback.showComingSoon(context),
                onPlaceholder: () =>
                    OrchestratorPlaceholderFeedback.showComingSoon(context),
              ),
              Expanded(
                child: ImportProjectSelectSourceBody(
                  onSelectLocal: () {
                    final ImportFlowStatus status = context
                        .read<ImportFlowCubit>()
                        .state
                        .status;
                    if (status == ImportFlowStatus.loading) {
                      return;
                    }
                    unawaited(context.read<ImportFlowCubit>().importLocal());
                  },
                  onPlaceholder: () =>
                      OrchestratorPlaceholderFeedback.showComingSoon(context),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

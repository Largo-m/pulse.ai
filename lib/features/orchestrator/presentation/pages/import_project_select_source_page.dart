import 'package:flutter/material.dart';

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
      child: ColoredBox(
        color: PulseColors.background,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            OrchestratorAppTopBar(
              isWorkspacesActive: true,
              onWorkspaces: () => Navigator.of(context).maybePop(),
              onImportProject: () =>
                  OrchestratorPlaceholderFeedback.showComingSoon(context),
              onPlaceholder: () =>
                  OrchestratorPlaceholderFeedback.showComingSoon(context),
            ),
            Expanded(
              child: ImportProjectSelectSourceBody(
                onPlaceholder: () =>
                    OrchestratorPlaceholderFeedback.showComingSoon(context),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

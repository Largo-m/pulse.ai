import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_placeholder_feedback.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_app_top_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_bottom_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_breadcrumb_bar.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/orchestrator_empty_state_body.dart';
import 'package:pulse_ai/shared/theme/pulse_theme_data.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';

final class OrchestratorEmptyPage extends StatelessWidget {
  const OrchestratorEmptyPage({super.key});

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
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  OrchestratorBreadcrumbBar(),
                  Expanded(child: _OrchestratorScrollableBody()),
                ],
              ),
            ),
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
      onPlaceholder: () =>
          OrchestratorPlaceholderFeedback.showComingSoon(context),
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

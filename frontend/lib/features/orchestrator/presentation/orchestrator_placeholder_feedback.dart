import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

abstract final class OrchestratorPlaceholderFeedback {
  static void showComingSoon(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(OrchestratorStrings.comingSoonMessage),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}

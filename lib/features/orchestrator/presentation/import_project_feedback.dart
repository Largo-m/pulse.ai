import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/import_project_strings.dart';

abstract final class ImportProjectFeedback {
  static void showImportFailure(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(ImportProjectStrings.importLocalFailureMessage),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}

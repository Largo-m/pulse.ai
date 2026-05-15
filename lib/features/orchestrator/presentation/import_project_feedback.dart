import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/import_project_strings.dart';

abstract final class ImportProjectFeedback {
  static String resolveFailureMessage(String? failureMessage) {
    if (failureMessage == null || failureMessage.trim().isEmpty) {
      return ImportProjectStrings.importLocalFailureMessage;
    }

    final String normalized = failureMessage.toLowerCase();
    if (normalized.contains('permission') ||
        normalized.contains('entitlement') ||
        normalized.contains('sandbox') ||
        normalized.contains('denied')) {
      return ImportProjectStrings.importLocalPermissionFailureMessage;
    }

    return ImportProjectStrings.importLocalFailureMessage;
  }

  static void showImportFailure(
    BuildContext context, {
    String? failureMessage,
  }) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(resolveFailureMessage(failureMessage)),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}

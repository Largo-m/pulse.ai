import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

final class PrdReviewUnsavedOverwriteDialog {
  const PrdReviewUnsavedOverwriteDialog._();

  static Future<bool?> show(BuildContext context) {
    return showDialog<bool>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text(OrchestratorStrings.prdReviewUnsavedOverwriteTitle),
          content: const Text(
            OrchestratorStrings.prdReviewUnsavedOverwriteBody,
          ),
          actions: <Widget>[
            Semantics(
              button: true,
              label:
                  OrchestratorStrings.prdReviewUnsavedOverwriteCancelSemantics,
              child: TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text(
                  OrchestratorStrings.prdReviewUnsavedOverwriteCancel,
                ),
              ),
            ),
            Semantics(
              button: true,
              label:
                  OrchestratorStrings.prdReviewUnsavedOverwriteConfirmSemantics,
              child: FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text(
                  OrchestratorStrings.prdReviewUnsavedOverwriteConfirm,
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

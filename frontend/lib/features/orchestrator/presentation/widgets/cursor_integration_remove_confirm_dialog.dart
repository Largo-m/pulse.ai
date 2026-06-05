import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

final class CursorIntegrationRemoveConfirmDialog {
  const CursorIntegrationRemoveConfirmDialog._();

  static Future<bool?> show(BuildContext context) {
    return showDialog<bool>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text(
            OrchestratorStrings.cursorSettingsRemoveConfirmTitle,
          ),
          content: const Text(
            OrchestratorStrings.cursorSettingsRemoveConfirmBody,
          ),
          actions: <Widget>[
            Semantics(
              button: true,
              label: OrchestratorStrings.cursorSettingsRemoveCancelSemantics,
              child: TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text(
                  OrchestratorStrings.cursorSettingsRemoveCancelButton,
                ),
              ),
            ),
            Semantics(
              button: true,
              label: OrchestratorStrings.cursorSettingsRemoveConfirmSemantics,
              child: FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text(
                  OrchestratorStrings.cursorSettingsRemoveConfirmButton,
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

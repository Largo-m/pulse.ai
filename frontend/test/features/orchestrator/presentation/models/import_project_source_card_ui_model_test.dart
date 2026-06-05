import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/features/orchestrator/presentation/import_project_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/import_project_source_card_ui_model.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';

void main() {
  group('ImportProjectSourceCardUiModel', () {
    test('retains provided copy and accent for local source', () {
      final ImportProjectSourceCardUiModel model =
          ImportProjectSourceCardUiModel(
            badgeLabel: ImportProjectStrings.localBadge,
            title: ImportProjectStrings.localTitle,
            body: ImportProjectStrings.localBody,
            features: const <String>[ImportProjectStrings.localFeatureDirectIo],
            buttonLabel: ImportProjectStrings.selectLocal,
            icon: Icons.folder_open_outlined,
            buttonTrailingIcon: Icons.arrow_forward,
            accentColor: PulseColors.primary,
            iconColor: PulseColors.primary,
            onPressed: () {},
          );

      expect(model.title, ImportProjectStrings.localTitle);
      expect(model.accentColor, PulseColors.primary);
      expect(model.features, hasLength(1));
    });

    test('supports secondary accent for remote source', () {
      final ImportProjectSourceCardUiModel model =
          ImportProjectSourceCardUiModel(
            badgeLabel: ImportProjectStrings.remoteBadge,
            title: ImportProjectStrings.remoteTitle,
            body: ImportProjectStrings.remoteBody,
            features: const <String>[ImportProjectStrings.remoteFeatureGitAuth],
            buttonLabel: ImportProjectStrings.selectRemote,
            icon: Icons.cloud_sync_outlined,
            buttonTrailingIcon: Icons.hub_outlined,
            accentColor: PulseColors.secondary,
            iconColor: PulseColors.secondary,
            onPressed: () {},
          );

      expect(model.accentColor, PulseColors.secondary);
    });
  });
}

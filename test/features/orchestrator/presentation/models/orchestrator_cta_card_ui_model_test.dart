import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/orchestrator_cta_card_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

void main() {
  group('OrchestratorCtaCardUiModel', () {
    test('holds provided title and button label', () {
      final OrchestratorCtaCardUiModel model = OrchestratorCtaCardUiModel(
        title: OrchestratorStrings.localProjectTitle,
        body: OrchestratorStrings.localProjectBody,
        icon: Icons.folder_open,
        accentBorderHover: const Color(0xFF000000),
        iconColor: const Color(0xFF000000),
        buttonLabel: OrchestratorStrings.localProjectButton,
        usesPrimaryButtonStyle: true,
        onPressed: _noop,
      );
      expect(model.title, OrchestratorStrings.localProjectTitle);
      expect(model.buttonLabel, OrchestratorStrings.localProjectButton);
    });

    test('usesPrimaryButtonStyle distinguishes primary vs tertiary CTA', () {
      final OrchestratorCtaCardUiModel primary = OrchestratorCtaCardUiModel(
        title: 'A',
        body: 'b',
        icon: Icons.add,
        accentBorderHover: const Color(0xFF000000),
        iconColor: const Color(0xFF000000),
        buttonLabel: 'X',
        usesPrimaryButtonStyle: true,
        onPressed: _noop,
      );
      final OrchestratorCtaCardUiModel secondary = OrchestratorCtaCardUiModel(
        title: 'A',
        body: 'b',
        icon: Icons.add,
        accentBorderHover: const Color(0xFF000000),
        iconColor: const Color(0xFF000000),
        buttonLabel: 'X',
        usesPrimaryButtonStyle: false,
        onPressed: _noop,
      );
      expect(primary.usesPrimaryButtonStyle, isTrue);
      expect(secondary.usesPrimaryButtonStyle, isFalse);
    });
  });
}

void _noop() {}

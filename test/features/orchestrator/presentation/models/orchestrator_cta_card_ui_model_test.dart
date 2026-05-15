import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/orchestrator_cta_card_ui_model.dart';

void main() {
  group('OrchestratorCtaCardUiModel', () {
    test('holds provided title and button label', () {
      final OrchestratorCtaCardUiModel model = OrchestratorCtaCardUiModel(
        title: 'Open Local Project',
        body: 'Body text',
        icon: Icons.folder_open,
        accentBorderHover: const Color(0xFF000000),
        iconColor: const Color(0xFF000000),
        buttonLabel: 'Initialize Local',
        usesPrimaryButtonStyle: true,
        onPressed: _noop,
      );
      expect(model.title, 'Open Local Project');
      expect(model.buttonLabel, 'Initialize Local');
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

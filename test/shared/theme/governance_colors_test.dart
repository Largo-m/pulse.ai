import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/shared/theme/tokens/governance_colors.dart';

void main() {
  group('GovernanceColors', () {
    test('background is fully opaque', () {
      expect(GovernanceColors.background.a, closeTo(1, 1e-6));
    });

    test('background is not transparent', () {
      expect(GovernanceColors.background, isNot(equals(Colors.transparent)));
    });
  });
}

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';

void main() {
  group('PulseColors', () {
    test('background is fully opaque', () {
      expect(PulseColors.background.a, closeTo(1, 1e-6));
    });

    test('background is not transparent', () {
      expect(PulseColors.background, isNot(equals(Colors.transparent)));
    });
  });
}

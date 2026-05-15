import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';

void main() {
  group('PulseDimensions', () {
    test('twoColumnBreakpoint is positive', () {
      expect(PulseDimensions.twoColumnBreakpoint, greaterThan(0));
    });

    test('maxContentWidth is not smaller than intro text width', () {
      expect(
        PulseDimensions.maxContentWidth,
        greaterThanOrEqualTo(PulseDimensions.maxIntroTextWidth),
      );
    });
  });
}

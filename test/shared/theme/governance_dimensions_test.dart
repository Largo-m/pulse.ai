import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/shared/theme/tokens/governance_dimensions.dart';

void main() {
  group('GovernanceDimensions', () {
    test('twoColumnBreakpoint is positive for responsive layout', () {
      expect(GovernanceDimensions.twoColumnBreakpoint, greaterThan(0));
    });

    test('maxContentWidth is not smaller than intro text width', () {
      expect(
        GovernanceDimensions.maxContentWidth,
        greaterThanOrEqualTo(GovernanceDimensions.maxIntroTextWidth),
      );
    });
  });
}

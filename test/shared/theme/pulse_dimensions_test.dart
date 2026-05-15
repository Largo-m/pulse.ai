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

    test('modal form and footer paddings are compact and positive', () {
      expect(PulseDimensions.modalFormBottomInset, greaterThan(0));
      expect(PulseDimensions.modalFooterVerticalPadding, greaterThan(0));
      expect(
        PulseDimensions.modalFormBottomInset,
        lessThan(PulseDimensions.horizontalInset),
      );
    });

    test('modal scroll body reserves chrome and allows a minimum extent', () {
      expect(PulseDimensions.modalScrollBodyMinExtent, greaterThan(0));
      expect(
        PulseDimensions.modalNonScrollingChromeHeightEstimate,
        greaterThan(0),
      );
      expect(
        680 - PulseDimensions.modalNonScrollingChromeHeightEstimate,
        greaterThanOrEqualTo(PulseDimensions.modalScrollBodyMinExtent),
      );
    });

    test(
      'orchestratorSidebarWidth is positive and distinct from chrome heights',
      () {
        expect(PulseDimensions.orchestratorSidebarWidth, greaterThan(0));
        expect(
          PulseDimensions.orchestratorSidebarWidth,
          isNot(equals(PulseDimensions.appTopBarHeight)),
        );
        expect(
          PulseDimensions.orchestratorSidebarWidth,
          isNot(equals(PulseDimensions.horizontalInset)),
        );
      },
    );
  });
}

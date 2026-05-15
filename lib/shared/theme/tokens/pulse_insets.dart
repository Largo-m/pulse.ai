import 'package:flutter/material.dart';

import 'pulse_dimensions.dart';

abstract final class PulseInsets {
  static const EdgeInsets pageScroll = EdgeInsets.all(
    PulseDimensions.pageScrollPadding,
  );

  static const EdgeInsets appTopBar = EdgeInsets.symmetric(
    horizontal: PulseDimensions.horizontalInset,
    vertical: PulseDimensions.topBarVerticalPadding,
  );

  static const EdgeInsets breadcrumbHorizontal = EdgeInsets.symmetric(
    horizontal: PulseDimensions.horizontalInset,
  );

  static const EdgeInsets textButton = EdgeInsets.symmetric(
    horizontal: PulseDimensions.textButtonHorizontalPadding,
    vertical: PulseDimensions.textButtonVerticalPadding,
  );

  static const EdgeInsets primaryTopBarButton = EdgeInsets.symmetric(
    horizontal: PulseDimensions.primaryButtonHorizontalPadding,
    vertical: PulseDimensions.primaryButtonVerticalPadding,
  );

  static const EdgeInsets ctaCard = EdgeInsets.all(
    PulseDimensions.ctaCardPadding,
  );

  static const EdgeInsets ctaButton = EdgeInsets.symmetric(
    horizontal: PulseDimensions.ctaButtonHorizontalPadding,
    vertical: PulseDimensions.ctaButtonVerticalPadding,
  );

  static const EdgeInsets watermark = EdgeInsets.all(
    PulseDimensions.watermarkPadding,
  );
}

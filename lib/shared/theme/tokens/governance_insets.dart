import 'package:flutter/material.dart';

import 'governance_dimensions.dart';

abstract final class GovernanceInsets {
  static const EdgeInsets pageScroll = EdgeInsets.all(
    GovernanceDimensions.pageScrollPadding,
  );

  static const EdgeInsets appTopBar = EdgeInsets.symmetric(
    horizontal: GovernanceDimensions.horizontalInset,
    vertical: GovernanceDimensions.topBarVerticalPadding,
  );

  static const EdgeInsets breadcrumbHorizontal = EdgeInsets.symmetric(
    horizontal: GovernanceDimensions.horizontalInset,
  );

  static const EdgeInsets textButton = EdgeInsets.symmetric(
    horizontal: GovernanceDimensions.textButtonHorizontalPadding,
    vertical: GovernanceDimensions.textButtonVerticalPadding,
  );

  static const EdgeInsets primaryTopBarButton = EdgeInsets.symmetric(
    horizontal: GovernanceDimensions.primaryButtonHorizontalPadding,
    vertical: GovernanceDimensions.primaryButtonVerticalPadding,
  );

  static const EdgeInsets ctaCard = EdgeInsets.all(
    GovernanceDimensions.ctaCardPadding,
  );

  static const EdgeInsets ctaButton = EdgeInsets.symmetric(
    horizontal: GovernanceDimensions.ctaButtonHorizontalPadding,
    vertical: GovernanceDimensions.ctaButtonVerticalPadding,
  );

  static const EdgeInsets watermark = EdgeInsets.all(
    GovernanceDimensions.watermarkPadding,
  );
}

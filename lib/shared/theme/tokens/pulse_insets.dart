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

  static const EdgeInsets filledActionButton = EdgeInsets.symmetric(
    horizontal: PulseDimensions.actionButtonHorizontalPadding,
    vertical: PulseDimensions.actionButtonVerticalPadding,
  );

  static const EdgeInsets primaryTopBarButton = filledActionButton;

  static const EdgeInsets ctaCard = EdgeInsets.all(
    PulseDimensions.ctaCardPadding,
  );

  static const EdgeInsets modalFormPadding = EdgeInsets.fromLTRB(
    PulseDimensions.horizontalInset,
    PulseDimensions.horizontalInset,
    PulseDimensions.horizontalInset,
    PulseDimensions.modalFormBottomInset,
  );

  static const EdgeInsets modalFooterPadding = EdgeInsets.fromLTRB(
    PulseDimensions.horizontalInset,
    PulseDimensions.modalFooterVerticalPadding,
    PulseDimensions.horizontalInset,
    PulseDimensions.modalFooterVerticalPadding,
  );

  static const EdgeInsets ctaButton = filledActionButton;

  static const EdgeInsets chromeIconButton = EdgeInsets.all(
    PulseDimensions.chromeIconButtonPadding,
  );

  static const EdgeInsets watermark = EdgeInsets.all(
    PulseDimensions.watermarkPadding,
  );

  static const EdgeInsets sidebarHeader = EdgeInsets.all(
    PulseDimensions.sidebarHeaderPadding,
  );

  static const EdgeInsets sidebarNav = EdgeInsets.symmetric(
    vertical: PulseDimensions.sidebarNavHorizontalPadding,
  );

  static const EdgeInsets sidebarTreeGroup = EdgeInsets.symmetric(
    horizontal: PulseDimensions.sidebarNavHorizontalPadding,
  );

  static const EdgeInsets sidebarTreeProjectRow = EdgeInsets.symmetric(
    horizontal: PulseDimensions.sidebarNavHorizontalPadding,
    vertical: PulseDimensions.sidebarTreeRowVerticalPadding,
  );

  static const EdgeInsets sidebarTreeAgentRow = EdgeInsets.symmetric(
    horizontal: PulseDimensions.sidebarNavHorizontalPadding,
    vertical: PulseDimensions.sidebarAgentRowVerticalPadding,
  );

  static const EdgeInsets workflowInstructionBarOuter = EdgeInsets.all(
    PulseDimensions.workflowInstructionBarOuterInset,
  );

  static const EdgeInsets workflowInstructionBarSuffix = EdgeInsets.only(
    right: PulseDimensions.workflowInstructionBarSuffixRightPadding,
    top: PulseDimensions.workflowInstructionBarSuffixVerticalPadding,
    bottom: PulseDimensions.workflowInstructionBarSuffixVerticalPadding,
  );

  static const EdgeInsets workflowInstructionBarApplyButtonHorizontal =
      EdgeInsets.symmetric(horizontal: PulseDimensions.sectionGapSm);

  static const EdgeInsets workflowStreamPanel = EdgeInsets.all(
    PulseDimensions.workflowInstructionBarOuterInset,
  );

  static const EdgeInsets workflowStreamChip = EdgeInsets.symmetric(
    horizontal: PulseDimensions.workflowStreamChipHorizontalPadding,
    vertical: PulseDimensions.workflowStreamChipVerticalPadding,
  );

  static const EdgeInsets prdReviewEditor = EdgeInsets.all(
    PulseDimensions.workflowInstructionBarOuterInset,
  );

  static const EdgeInsets prdReviewContextHeader = EdgeInsets.symmetric(
    horizontal: PulseDimensions.workflowInstructionBarOuterInset,
    vertical: PulseDimensions.sectionGapSm,
  );

  static const EdgeInsets prdReviewActionBar = EdgeInsets.all(
    PulseDimensions.workflowInstructionBarOuterInset,
  );

  static const EdgeInsets prdReviewUserEditedBadge = EdgeInsets.symmetric(
    horizontal: PulseDimensions.prdReviewUserEditedBadgeHorizontalPadding,
    vertical: PulseDimensions.prdReviewUserEditedBadgeVerticalPadding,
  );
}

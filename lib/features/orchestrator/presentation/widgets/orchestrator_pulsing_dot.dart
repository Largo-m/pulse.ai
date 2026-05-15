import 'package:flutter/material.dart';

import 'package:pulse_ai/shared/theme/tokens/governance_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_dimensions.dart';

final class OrchestratorPulsingDot extends StatefulWidget {
  const OrchestratorPulsingDot({super.key});

  @override
  State<OrchestratorPulsingDot> createState() => _OrchestratorPulsingDotState();
}

class _OrchestratorPulsingDotState extends State<OrchestratorPulsingDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(
      milliseconds: GovernanceDimensions.pulsingDurationMs,
    ),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: Tween<double>(
        begin: GovernanceDimensions.pulsingOpacityLow,
        end: GovernanceDimensions.pulsingOpacityHigh,
      ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeInOut)),
      child: const SizedBox(
        width: GovernanceDimensions.standbyDotSize,
        height: GovernanceDimensions.standbyDotSize,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: GovernanceColors.tertiary,
            shape: BoxShape.circle,
          ),
        ),
      ),
    );
  }
}

import React from 'react';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import { isEdgeBrowserProfile } from '../lib/browserProfile';

/**
 * @typedef {{
 *   children?: import('react').ReactNode,
 *   className?: string,
 *   hoverEffect?: boolean,
 *   as?: import('react').ElementType,
 * }} GlassCardProps
 */

/** @param {GlassCardProps & Record<string, unknown>} props */
const GlassCard = ({ children, className, hoverEffect = true, as: Component = motion.div, ...props }) => {
  const reducedEffects = isEdgeBrowserProfile();

  return (
    <Component
      initial={reducedEffects ? false : { opacity: 0, y: 10 }}
      animate={reducedEffects ? undefined : { opacity: 1, y: 0 }}
      exit={reducedEffects ? undefined : { opacity: 0, y: 10 }}
      transition={reducedEffects ? undefined : { duration: 0.4, ease: "easeOut" }}
      className={clsx(
        "glass-card relative overflow-hidden",
        hoverEffect && "hover:shadow-[0_12px_40px_rgba(179,133,79,0.15)] hover:-translate-y-[2px]",
        className
      )}
      data-reduced-effects={reducedEffects ? 'true' : 'false'}
      {...props}
    >
      {/* Internal shine effect */}
      <div className="absolute inset-0 bg-gradient-to-tr from-white/20 via-transparent to-transparent opacity-0 transition-opacity duration-300 hover:opacity-100 pointer-events-none" />

      {children}
    </Component>
  );
};

export default GlassCard;

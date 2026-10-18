import { useEffect, useRef, type ButtonHTMLAttributes, type CSSProperties } from 'react'
import { ShaderButtons } from '@designcodeio/threeui/components/ShaderButtons'
import '@designcodeio/threeui/style.css'

type TactileActionProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'className'> & {
  children: string
  size?: 'regular' | 'compact' | 'micro' | 'wide'
  className?: string
}

const compactFrameStyle: CSSProperties = {
  position: 'absolute',
  top: 0,
  left: 0,
  width: '147.0588%',
  height: '145.8333%',
  maxWidth: 'none',
  transform: 'scale(0.68)',
  transformOrigin: 'top left',
  pointerEvents: 'none',
}

const regularFrameStyle: CSSProperties = {
  position: 'absolute',
  inset: 0,
  width: '100%',
  height: '100%',
  pointerEvents: 'none',
}

export default function TactileAction({
  children,
  className = '',
  size = 'regular',
  type = 'button',
  ...buttonProps
}: TactileActionProps) {
  const frameHost = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const host = frameHost.current
    if (!host) return

    const hideFrameFromKeyboard = () => {
      const frame = host.querySelector('iframe')
      if (!frame) return
      frame.tabIndex = -1
      frame.setAttribute('aria-hidden', 'true')
    }

    hideFrameFromKeyboard()
    const observer = new MutationObserver(hideFrameFromKeyboard)
    observer.observe(host, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [])

  return (
    <span className={`pg-tactile-action pg-tactile-action--${size} ${className}`.trim()} ref={frameHost}>
      <ShaderButtons
        variant="tactile-button"
        mode="dark"
        hue={145}
        saturation={0.72}
        brightness={0.52}
        className="pg-tactile-action__shader"
        style={size === 'micro' || size === 'compact' ? compactFrameStyle : regularFrameStyle}
      />
      <button {...buttonProps} className="pg-tactile-action__button" type={type}>
        <span className="pg-tactile-action__label">{children}</span>
        <span className="pg-tactile-action__arrow" aria-hidden="true">↗</span>
      </button>
    </span>
  )
}

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MarkdownText } from './MarkdownText'

describe('MarkdownText images', () => {
  it('never renders an <img>, so model text cannot make the browser fetch a URL', () => {
    const { container } = render(<MarkdownText text={'Before ![a chart](https://evil.example/pixel.png) after ![](https://evil.example/p2.png)'} />)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('a chart')).toBeInTheDocument()
    expect(container.innerHTML).not.toContain('evil.example')
  })

  it('still renders ordinary markdown', () => {
    render(<MarkdownText text={'## Heading\n\n**bold** text'} />)
    expect(screen.getByRole('heading', { name: 'Heading' })).toBeInTheDocument()
    expect(screen.getByText('bold')).toBeInTheDocument()
  })
})

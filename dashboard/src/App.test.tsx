import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import App from './App'

test('renders the deterministic demo entry point',()=>{
  render(<App />)
  expect(screen.getByText('Detect pressure before it cascades.')).toBeTruthy()
  expect(screen.getByRole('button',{name:'Analyze incident'})).toBeTruthy()
})


declare module 'd3-force' {
  export interface SimulationNodeDatum {
    index?: number
    x?: number
    y?: number
    vx?: number
    vy?: number
    fx?: number | null
    fy?: number | null
  }

  export interface SimulationLinkDatum<NodeDatum extends SimulationNodeDatum> {
    source: NodeDatum | string | number
    target: NodeDatum | string | number
    index?: number
  }

  export interface Simulation<NodeDatum extends SimulationNodeDatum, LinkDatum extends SimulationLinkDatum<NodeDatum>> {
    force(name: string, force: unknown): Simulation<NodeDatum, LinkDatum>
    alpha(value: number): Simulation<NodeDatum, LinkDatum>
    alphaDecay(value: number): Simulation<NodeDatum, LinkDatum>
    velocityDecay(value: number): Simulation<NodeDatum, LinkDatum>
    on(typename: 'tick', listener: () => void): Simulation<NodeDatum, LinkDatum>
    stop(): void
  }

  export interface ForceLink<NodeDatum extends SimulationNodeDatum, LinkDatum extends SimulationLinkDatum<NodeDatum>> {
    id(accessor: (node: NodeDatum) => string | number): ForceLink<NodeDatum, LinkDatum>
    distance(distance: number | ((link: LinkDatum, index: number, links: LinkDatum[]) => number)): ForceLink<NodeDatum, LinkDatum>
    strength(value: number): ForceLink<NodeDatum, LinkDatum>
  }

  export interface ForceManyBody<NodeDatum extends SimulationNodeDatum> {
    strength(value: number | ((node: NodeDatum, index: number, nodes: NodeDatum[]) => number)): ForceManyBody<NodeDatum>
  }

  export interface ForceCollide<NodeDatum extends SimulationNodeDatum> {
    strength(value: number): ForceCollide<NodeDatum>
    iterations(value: number): ForceCollide<NodeDatum>
  }
  export interface ForceCenter<NodeDatum extends SimulationNodeDatum> {
    strength(value: number): ForceCenter<NodeDatum>
  }
  export interface ForceX<NodeDatum extends SimulationNodeDatum> {
    strength(value: number): ForceX<NodeDatum>
  }
  export interface ForceY<NodeDatum extends SimulationNodeDatum> {
    strength(value: number): ForceY<NodeDatum>
  }

  export function forceSimulation<NodeDatum extends SimulationNodeDatum>(
    nodes?: NodeDatum[],
  ): Simulation<NodeDatum, SimulationLinkDatum<NodeDatum>>
  export function forceCenter<NodeDatum extends SimulationNodeDatum>(x?: number, y?: number): ForceCenter<NodeDatum>
  export function forceCollide<NodeDatum extends SimulationNodeDatum>(
    radius?: number | ((node: NodeDatum, index: number, nodes: NodeDatum[]) => number)
  ): ForceCollide<NodeDatum>
  export function forceLink<NodeDatum extends SimulationNodeDatum, LinkDatum extends SimulationLinkDatum<NodeDatum>>(
    links?: LinkDatum[],
  ): ForceLink<NodeDatum, LinkDatum>
  export function forceManyBody<NodeDatum extends SimulationNodeDatum>(): ForceManyBody<NodeDatum>
  export function forceX<NodeDatum extends SimulationNodeDatum>(x?: number): ForceX<NodeDatum>
  export function forceY<NodeDatum extends SimulationNodeDatum>(y?: number): ForceY<NodeDatum>
}

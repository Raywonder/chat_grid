# Indiginous world cars — 2026-07-26

The requested “Injen Simulator” appears to be Ange Yaghi's Engine Simulator
(https://github.com/ange-yaghi/engine-sim). It is an internal-combustion
engine/audio simulator, not a drivable-world framework. Indiginous therefore
uses it as an engine/audio reference while keeping world movement, seats,
ownership, and accessibility native to the world code.

The first world slice adds three shared public vehicles in Main City: two cars
and one SUV. A user can activate a vehicle to sit in it, use movement keys to
drive it, and activate it again to get out. The authoritative server moves the
vehicle item with its driver, so other users receive the same world position.
Each vehicle has one seat, allowing several people to drive independently.

No external Engine Simulator binaries or source were copied into the product.
Generated/recorded engine sounds remain a separate asset pass; no placeholder
sound is presented as a finished engine asset.

Verification: Python compilation, 30 server persistence/house tests, and the
client production build passed. Live service deployment, multi-user browser
proof, and physical audio testing remain separate release steps.

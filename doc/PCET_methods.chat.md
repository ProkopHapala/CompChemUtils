# USER

Can I use cheap DFTB or g-xTB method to scan the PES plot the n+1\n-1 or excited PES estimate of to see how it looks and in which Regime I'm (if I'm in complicated regime where CASSCF\TDDFT is required or simple...).

I know that PES will be quantitatively wrong but the topological features like crossing and conical intersection should be robust even with cheap methods...
How exactly to do that?
What exactly I should look for?

If I want to calculate Proton-coupled electron transfer between heterocyclic molecules. What level of theory it requires. Would normal DFT or even DFTB, Grimme xTB gfn2 or g-xTB be ok to get energy barriers? What would be missing? Or do I need som CASSCF, muktireferce calculations? I mostly want to know the energy barriers for many different molecules. I mostly want transfer of hydrogen induced by electric field or electron injection there I perhaps do not need TDDFT. If I want transfer of proton induced by optical excitation then I perhaps need TDDFT. But I want to do high throughput screening, and for that purpose I would like some semiemperical approach, maybe like zindo or something like semiemperical time-dependent DFTB (is there something like that?)

---

# Gemini

Calculating Proton-Coupled Electron Transfer (PCET) or pure proton/hydrogen transfer in heterocyclic systems across large chemical libraries requires a careful trade-off between computational speed and physical accuracy. Because your primary goal is a **high-throughput screening (HTS)** workflow to evaluate energy barriers across many molecules, your choice of method depends heavily on how the process is triggered.

## 1. Ground State, Electric Field, or Electron Injection

When the transfer is induced by an applied electric field or an injected electron (forming a radical ion), the process stays on the **ground-state potential energy surface (PES)** of that specific charge state.

### Do you need CASSCF / Multireference?

**Usually, no.** For closed-shell heterocycles or well-defined radical ions, single-reference methods are entirely adequate. Heterocyclic hydrogen bonds do not typically involve the severe static correlation found in transition metal complexes or bond-breaking that yields diradicals.

### Can you use DFT?

Standard Density Functional Theory (DFT) is the reliable benchmark here.

* **The Missing Piece:** Standard GGAs (like PBE) and even the global hybrid B3LYP systematically **underestimate reaction barriers**. This is caused by self-interaction error (SIE), which over-stabilizes the delocalized transition state.
* **The Fix:** You should use **range-separated hybrid functionals** like **$\omega$B97X-D** or **M06-2X**. They retain exact long-range Hartree-Fock exchange, which correctly localizes the electron/proton and yields highly accurate barrier heights.

### Can you use Semiempirical (DFTB, GFN2-xTB, g-xTB)?

For a high-throughput screening of barriers, normal semiempirical methods are risky, but newer developments offer a viable path forward:

* **Normal DFTB / GFN2-xTB:** These methods generally **fail to provide accurate absolute barrier heights**. Because GFN2-xTB emulates a GGA functional and uses a minimal basis set, it routinely underestimates proton-transfer barriers (sometimes to the point of turning a shallow barrier into a barrierless transition). However, GFN2-xTB is *excellent* for rapid geometry optimizations and generating the reaction paths (e.g., using Nudged Elastic Band methods).
* **g-xTB:** This is a much better candidate. Grimme's general-purpose extended tight-binding method (**g-xTB**) incorporates approximate range-separated Fock exchange. It explicitly targets reaction barriers and significantly reduces the systematic underestimation seen in GFN2.
* **The HTS Strategy:** Use **GFN2-xTB** or **g-xTB** to rapidly optimize the reactant, product, and transition-state guesses. Then, run a single-point energy calculation using a range-separated hybrid DFT functional ($\omega$B97X-D/def2-TZVP) to get the true barrier height.

## 2. Optically Induced Transfer (Excited States)

If the proton transfer happens after absorbing a photon—often called Excited-State Intramolecular Proton Transfer (**ESIPT**)—you shift to the **excited-state PES**.

### Do you need TD-DFT?

**Yes.** Standard ground-state DFT or semiempirical methods will completely miss the physics, as the acidity ($pK_a$) and electron density of heterocycles shift dramatically upon optical excitation.

### Is there a Semiemperical Time-Dependent DFTB?

Yes, **TD-DFTB** (Time-Dependent Density Functional Tight Binding) exists and is actively used for this purpose.

* Software packages like **DFTB+** and **Amsterdam Modeling Suite (AMS)** have robust TD-DFTB implementations that can calculate excited-state energies, gradients, and track ESIPT pathways.
* **ZINDO (ZINDO/S):** While classic ZINDO is incredibly fast for predicting UV-Vis absorption spectra of organic molecules, it lacks analytical excited-state gradients in most standard packages. This makes optimizing excited-state geometries or running transition-state searches along the ESIPT path very difficult.

## Summary Screening Blueprint

For an efficient high-throughput screening workflow, consider a hierarchical screening strategy:

| Trigger | Step 1: Geometry & Path Generation (Fast) | Step 2: Energy & Barrier Evaluation (Accurate) |
| --- | --- | --- |
| **Electric Field / Electron Injection** | **g-xTB** or **GFN2-xTB** (NEB / String method to find the TS) | Single-point **$\omega$B97X-D** or **M06-2X** (with a split-valence basis set like def2-SVP or def2-TZVP) |
| **Optical Excitation (ESIPT)** | **TD-DFTB** (To relax the $S_1$ state and scan the proton transfer coordinate) | Single-point **TD-DFT** (using a range-separated hybrid functional to correct charge-transfer errors) |

### What Else Might Be Missing?

1. **Nuclear Quantum Tunneling:** Because hydrogen is so light, it often tunnels through narrow potential barriers rather than going over them. If your calculated classical barriers are high but the experimental rates are fast, you may need a simple correction like the Wigner or Eckart transmission coefficient.
2. **Solvent/Environment Effects:** Heterocyclic proton transfers are incredibly sensitive to the dielectric constant of the surroundings or explicit hydrogen-bonding networks. Ensure your screening includes a continuum solvation model (like ALPB in xTB or CPCM/SMD in DFT).

---

# ChatGPT 5.5

For **high-throughput PCET barriers**, I would **not start with CASSCF**. I would use a **tiered workflow**.

### Practical answer

For heterocyclic H/proton transfer:

**Good screening level**
`GFN2-xTB / g-xTB + NEB/string + single-point DFT correction on selected points`

This is probably the best cost/benefit for many molecules. GFN2-xTB was parametrized broadly and performs relatively well for H-bonding, proton affinities, and H-transfer barriers, but approximate methods still show errors of order **10–20 kJ/mol** or more depending on chemistry. Recent proton-transfer benchmarks found GFN2-xTB and DFTB3 among the better cheap methods, but also emphasized missing polarization/H-bond accuracy from small basis/minimal-basis models. ([American Chemical Society Publications][1])

**Better reference level**
`ωB97X-D / CAM-B3LYP / PBE0-D4 / r2SCAN-3c`
with at least `def2-SVP` for scans and `def2-TZVP` single points.

For **field-induced** or **electron-injection-induced** proton transfer, ground-state DFT or constrained/charged-state DFT is often enough. You need the PES for the relevant charge state, e.g.

[
E_\mathrm{neutral}(R),\quad E_{\mathrm{anion/cation}}(R),\quad E_{\mathrm{field}}(R)
]

No TDDFT unless the electron injection creates a genuine electronically excited state rather than just a different redox state.

### What cheap methods miss

Main missing physics in DFTB/xTB for PCET:

1. **Proton barrier shape**: minimal basis and parametrized repulsion can distort short strong H-bonds and transition states.
2. **Charge localization / self-interaction**: important when electron injection changes whether proton transfer is favorable.
3. **Electric-field response**: polarizability and Stark shifts may be too crude.
4. **Nonadiabatic PCET coupling**: if electron and proton transfer are concerted but not adiabatic, a single PES barrier is incomplete.
5. **Tunneling / ZPE**: proton barriers need ZPE correction; tunneling can dominate at low T.
6. **Environment / substrate screening**: for charged heterocycles on surfaces this may be as important as the molecule.

### Do you need multireference?

Usually **no** for ordinary heterocycle proton transfer on one charge surface. You may need CASSCF/CASPT2/NEVPT2 only if:

* bond breaking creates near-degenerate diradical/zwitterionic states,
* proton transfer strongly changes aromaticity with nearly crossing electronic configurations,
* optical excitation involves conical intersections or (S_1/S_0) crossings,
* DFT gives spin contamination, fractional-charge artifacts, or multiple unstable SCF solutions.

For many heterocycles, **range-separated hybrid DFT is more useful than CASSCF** as a reference.

### Optical excitation

Here TDDFT or semiempirical excited-state methods become relevant.

There **is TD-DFTB**. DFTB+ has linear-response TD-DFTB recipes for excited-state properties, and recent DFTB+ development includes TD-DFTB implementations. ([dftbplus-recipes.readthedocs.io][2])

There are also Grimme-style fast excited-state methods: **sTDA/sTD-DFT with xTB ground states**, including `sTDA-xTB`, meant for ultrafast excited-state screening. ([chemie][3])

For optical proton transfer screening, I would use:

[
S_0 \text{ barrier: xTB/g-xTB}
]
[
S_1 \text{ driving force: sTDA-xTB or TD-DFTB}
]
then validate top candidates with TDDFT, preferably range-separated TDDFT.

### Suggested high-throughput protocol

1. Generate donor–acceptor geometries and H-bond motifs with **GFN2-xTB/g-xTB**.
2. Compute proton-transfer path with constrained H coordinate or NEB.
3. Add electric field or charged state explicitly.
4. Rank by:
   [
   \Delta E_\mathrm{PT},\quad E^\ddagger_\mathrm{PT},\quad d_{\mathrm{N/O}\cdots\mathrm{N/O}},\quad \Delta q,\quad \Delta\mu
   ]
5. Recompute top 5–10% with DFT.
6. For optical cases, screen vertical excitations with **sTDA-xTB / TD-DFTB**, then TDDFT on promising cases.
7. Use CASSCF only as a diagnostic for weird cases, not as the screening engine.

My bias: for your purpose, use **xTB/g-xTB as a fast geometry/barrier generator**, but do not trust absolute barriers without **DFT recalibration on a representative subset**.

[1]: https://pubs.acs.org/doi/10.1021/acs.jctc.8b01176?utm_source=chatgpt.com "GFN2-xTB—An Accurate and Broadly Parametrized Self ..."
[2]: https://dftbplus-recipes.readthedocs.io/en/latest/linresp/index.html?utm_source=chatgpt.com "Linear response excitations - DFTB+ recipes - Read the Docs"
[3]: https://www.chemie.uni-bonn.de/grimme/de/software/stda/stda_manual.pdf/%40%40download/file/stda_manual.pdf?utm_source=chatgpt.com "sTDA - User Manual - Chemie@uni-bonn.de"

---

# DeepSeek-V4-pro

For a high-throughput screening of proton-coupled electron transfer (PCET) barriers in heterocyclic molecules, you can certainly use fast semiempirical methods to filter candidates, but you must be aware of their limitations. Here’s a breakdown of what each level of theory can and cannot do for your specific scenarios.

### 1. Ground-state PCET (electric field / electron injection)

You are driving the reaction without optical excitation, so the process evolves on the **electronic ground state**. You want the activation barrier for the concerted (or stepwise) proton–electron transfer.

| Method | Suitable for screening? | Key limitations |
|--------|------------------------|-----------------|
| **GFN2-xTB / DFTB** | ✅ **Yes, for rough pre-screening** | Barriers can easily be off by **5–10 kcal/mol** (sometimes more) due to the minimal basis and the way the Hamiltonian is approximated. Proton transfer barriers, in particular, are often over- or underestimated. Charge-transfer character and delicate hydrogen-bond energetics are not always reliably captured. |
| **Standard DFT** (e.g., B3LYP, PBE0) | ⚠️ **Use with caution** | Delocalisation error can artificially lower barriers and smear out charge separation. Range‑separated hybrids (ωB97X‑D, M11, CAM‑B3LYP) are much safer. Dispersion corrections (D3/D4) are essential for the non‑covalent interactions that govern pre‑organisation. |
| **High‑grade DFT** (ωB97M‑V, DLPNO‑CCSD(T) as benchmark) | ✅ **Recommended for final numbers** | Cost scales with system size but gives barriers typically within 1–2 kcal/mol of reference for organic PCET, provided static correlation is absent. |
| **Multireference** (CASSCF, CASPT2, NEVPT2) | ❌ **Overkill for most heterocyclic PCET** | Needed only if the transition state has substantial **diradical character** (e.g., a homolytically cleaving bond with two nearly degenerate open‑shell configurations). Simple H‑atom transfers between closed‑shell heterocycles rarely require this. If your molecules contain transition metals or strained biradicaloids, a quick T1 diagnostic or fractional-occupation test from DFT can tell you whether MR is necessary. |

**What is missing** when you use only a *semiempirical* or even *DFT* adiabatic barrier?
- **Nuclear quantum effects** – proton tunneling and zero‑point energy often lower the effective barrier by 2–5 kcal/mol. You can add these with a one‑dimensional WKB correction or ring‑polymer instanton, but the underlying PES must be accurate.
- **Nonadiabaticity** – if the electron transfer is significantly slower than the proton motion, the reaction is best described by a **vibronically nonadiabatic** rate constant (Marcus‑like theory for PCET). A simple adiabatic barrier is then insufficient; you need the electronic coupling, solvent reorganisation energy, and proton vibrational wavefunctions.
- **Solvent effects** – implicit solvent (PCM, SMD) is straightforward to include at DFT level and is also available in xTB (GBSA/ALPB models). Explicit solvent molecules that actively participate in the proton wire may be crucial for heterocyclic PCET.

**Practical high‑throughput workflow for ground‑state PCET:**
1. Generate conformers and guess TS with **GFN2‑xTB** (extremely fast, handles electric fields via the `EFIELD` keyword).
2. Refine the lowest‑energy path with **ωB97X‑D3/def2‑SVP** (or an even smaller basis) and confirm the TS with a frequency calculation.
3. Single‑point energy with a larger basis (def2‑TZVPP) and add tunneling corrections if needed.
This way you screen thousands of candidates with xTB and only run DFT on the most promising ones.

### 2. Photoinduced PCET (optical excitation → proton transfer)

Here the reaction occurs on an **excited state** potential energy surface, so you cannot avoid an excited‑state method. The same semiempirical philosophy applies, and yes, **fast excited‑state semiempirical methods exist**.

| Method | Availability | Remarks |
|--------|--------------|---------|
| **TD‑DFTB** | DFTB+ (with the `tdexcite` module) | A time‑dependent extension of DFTB. Good for vertical excitations and excited‑state gradient calculations. Can locate excited‑state minima and conical intersections. Accuracy is limited by the DFTB ground‑state reference; charge‑transfer states may be poorly described. |
| **sTDA‑xTB** (simplified Tamm‑Dancoff approximation with GFN2‑xTB) | Available in the `xtb` program (version ≥ 6.5, `--gfn2 --tda`) or via standalone `sTDA` codes | Combines GFN2‑xTB with a simplified TDA/CIS framework. Extremely fast (microseconds per excitation) and often surprisingly good for organic chromophores. It includes electrostatic embedding and can treat large heterocyclic assemblies. |
| **ZINDO/S** | ORCA, Gaussian, etc. | An old but still popular semiempirical CIS method parametrised for spectroscopy. It can be used for ground‑ and excited‑state geometry optimisations, but its energetics are less reliable than sTDA‑xTB for modern applications. |

**Recommendation for photo‑PCET screening:**
- Use **sTDA‑xTB** (GFN2‑xTB‑TDA) to map the excited‑state PES and locate the minimum‑energy crossing point or the proton‑transfer TS on the excited surface. It will give you qualitative trends (e.g., which heterocycle pair has the lowest excited‑state barrier) at a fraction of the cost of TD‑DFT.
- Validate a handful of hits with **TD‑DFT** (e.g., ωB97X‑D3, CAM‑B3LYP) including a state‑tracking algorithm. For excited‑state proton transfer, the bright state is often of ππ* character, which TD‑DFT describes well as long as no doubly excited character is involved. If the excited state acquires significant charge‑transfer or Rydberg character, range‑separated functionals are mandatory.

### 3. What about xTB or DFTB alone – can you trust the barriers for screening?

Yes, if you only need to **rank** molecules by barrier height and accept that the absolute numbers might be shifted. GFN2‑xTB has been parametrised on thousands of reaction energies and barriers, and for “typical” organic proton transfers it often reproduces **trends** within chemical series. However, when the proton is shared between two different heterocycles with very different proton affinities, the barrier can become extremely sensitive to the balance of covalent and non‑covalent interactions – precisely where xTB can fail. Therefore:

- **For pure ranking**: xTB is a sensible first pass, but discard it if you need reliable absolute rate estimates.
- **For publication‑quality barriers**: Always follow up with DFT (and benchmark a few cases with DLPNO‑CCSD(T) if possible).

### Summary table of methods and their “missing” ingredients

| Method | Missing for PCET |
|--------|------------------|
| **GFN2‑xTB / DFTB** | Quantitative accuracy, charge‑transfer description, nuclear quantum effects, sometimes correct TS connectivity |
| **DFT** (good functional) | Nuclear quantum effects, nonadiabatic couplings (for nonadiabatic PCET), occasionally static correlation |
| **CASSCF/NEVPT2** | Not missing for organic PCET, but far too expensive; includes static correlation you mostly don’t need |
| **TD‑DFTB / sTDA‑xTB** | Accuracy for charge‑transfer excited states, double excitations, accurate excited‑state gradients; nuclear quantum effects |

In short, for a high‑throughput campaign:
- **Ground state**: GFN2‑xTB → DFT (range‑separated hybrid) → benchmark.
- **Excited state**: sTDA‑xTB → TD‑DFT → possibly wavefunction‑based excited‑state method (e.g., STEOM‑DLPNO‑CCSD) for final checks.

Both workflows will let you process hundreds of heterocyclic pairs while keeping the computational cost manageable.

---

# Kimi 2.6 chat

For high-throughput screening of proton-coupled electron transfer (PCET) energy barriers, the choice of method depends heavily on the mechanism and what physics you need to capture. Let me break this down practically:

## For Field/Electron-Injection Induced PCET (Ground State)

**Semiempirical approaches that can work:**

- **GFN2-xTB / GFN1-xTB**: Surprisingly capable for ground-state proton transfer barriers if the reaction is mostly thermally activated and doesn't involve strong electronic correlation. The hydrogen-bonding corrections in GFN2 help. For pure proton transfer (H⁺), this is often acceptable for screening.

- **DFTB with 3rd-order corrections and D3 dispersion**: Better than standard DFTB for barrier heights, but you need to validate against DFT for your specific heterocycle class first.

- **Normal DFT (e.g., B3LYP, ωB97X-D, M06-2X)**: The minimum reliable standard. For barriers, **hybrid functionals with dispersion corrections** are strongly preferred. GGA functionals (PBE, BLYP) typically underestimate barriers by 3-5 kcal/mol.

**What would be missing with semiempirical/DFTB:**
- Accurate description of the transition state (often delocalized proton character)
- Electronic coupling between diabatic states if PCET is concerted and non-adiabatic
- Charge localization/delocalization effects in aromatic heterocycles
- Dispersion interactions (though GFN2 and DFTB-D3 partially address this)

## For Optically Induced PCET (Excited State)

You are correct that this requires excited-state methods. Options for screening:

- **sTDA-xTB** (Grimme's simplified Tamm-Dancoff approach built on xTB): This is exactly the kind of semiempirical TD-DFT-like method you asked about. It's designed for fast excited-state screening. Available in xtb and ORCA.

- **TD-DFTB**: Exists (e.g., in DFTB+ and some ORCA implementations), but parameter availability for heterocycles is patchy.

- **ZINDO/S**: Very fast but generally poor for barrier heights; better for spectra. Not recommended for quantitative barriers.

- **CIS(D) or ADC(2)** in semiempirical form: Not really practical for high-throughput.

## Do You Need Multireference?

**Probably not for screening**, but with caveats:

- If the PCET involves **bond homolysis** (H-atom transfer rather than H⁺/e⁻ sequential transfer), or if the transition state has **significant diradical character**, single-reference methods fail. Check with **UKS stability analysis** or **ΔSCF broken-symmetry** approaches first.

- For heterocycles with low-lying excited states (e.g., extended π-systems, certain N-heterocycles), **TDDFT can fail** due to charge-transfer state problems. Range-separated hybrids (ωB97X-D, CAM-B3LYP) help.

- **CASSCF/CASPT2 or NEVPT2**: Only needed if you observe:
  - Near-degeneracy of configurations at the TS
  - Strong static correlation in the reactant/product (e.g., certain quinones, phenoxyl radicals)
  - Bond-breaking regions where DFT spin-contamination is severe

## Practical High-Throughput Strategy

**Tier 1 (Screening, thousands of molecules):**
- Ground state: GFN2-xTB with metadynamics or NEB for barriers
- Excited state: sTDA-xTB for vertical excitation energies and preliminary excited-state PES

**Tier 2 (Validation, hundreds of molecules):**
- Ground state: DFT (ωB97X-D/def2-TZVP) with NEB or dimer method
- Excited state: TD-DFT with the same functional, or ADC(2) for problematic cases

**Tier 3 (Accuracy, tens of molecules):**
- DLPNO-CCSD(T) or CASPT2/NEVPT2 for final barriers where single-reference is questionable

## Specific Recommendations

1. **For field-induced PCET**: Start with **GFN2-xTB + metadynamics** (available in xtb). Validate on 5-10 representative systems against **ωB97X-D3/def2-TZVP**. If GFN2 barriers are within 2-3 kcal/mol, use it for screening.

2. **For optical PCET**: Use **sTDA-xTB** for initial excited-state PES scans. For heterocycles with possible CT states, validate with **TD-CAM-B3LYP** or **ADC(2)**.

3. **Check for multireference character**: Run a few systems at the DFT level with **UKS broken-symmetry** and check **⟨S²⟩** at the TS. If severe spin contamination (>0.5 above expected), or if you see orbital instability, then consider (CAS(2,2) or similar) as a spot-check—not for the full screening.

4. **What DFTB/xTB misses for barriers**: 
   - Proton tunneling (use Wigner or Eckart corrections afterward)
   - Non-adiabatic coupling if electron and proton transfer are concerted
   - Explicit solvent polarization (use implicit PCM/COSMO at DFT level for validation)

## Summary Table

| Method | Speed | Barrier Quality | Excited State | Best For |
|--------|-------|-----------------|---------------|----------|
| GFN2-xTB | Very fast | Fair (validate!) | No | Ground-state screening |
| sTDA-xTB | Very fast | Approximate | Yes | Excited-state screening |
| DFTB3-D3 | Fast | Fair | Limited (parameter-dependent) | Ground-state screening |
| DFT (hybrid-D3) | Moderate | Good | TD-DFT available | Validation & final barriers |
| CASSCF/CASPT2 | Slow | Excellent | Yes | Spot-checks for correlation |

**Bottom line**: For high-throughput screening of PCET barriers, start with **GFN2-xTB for ground state** and **sTDA-xTB for excited state**, but **calibrate against hybrid DFT on a representative subset**. Reserve multireference methods for cases where single-reference diagnostics fail, not as the default screening tool.

---

# Mistral

For **proton-coupled electron transfer (PCET) energy barriers** in heterocyclic molecules, here’s a concise, practical guide based on current literature and benchmarks:

### **🔹 Ground-State PCET (Electric Field/Electron Injection)**
**✅ DFT is the workhorse** and generally sufficient for:
- **Energy barriers** (reaction free energy, reorganization energy, vibronic coupling)
- **Geometries** and **redox potentials** (agrees with experiment for many systems)
- **Concerted vs. sequential mechanisms** (DFT can distinguish these in most cases)

**✅ Semi-empirical methods for high-throughput screening:**
| Method          | Barrier Accuracy (MUE) | Notes                                                                 |
|-----------------|------------------------|-----------------------------------------------------------------------|
| **GFN2-xTB**    | ~13.5 kJ/mol          | **Best overall** for proton transfer barriers; includes N–H corrections |
| **DFTB3**       | ~15.2 kJ/mol          | Strong for carboxylates, thiols, water clusters; SCC improves accuracy |
| **DFTB2-NH**    | Reasonable            | Explicit N–H binding corrections help for heterocycles               |
| **PM6/7, RM1**  | Varies by group        | Less consistent than xTB/DFTB for barriers                           |

**⚠️ What you’d miss with semi-empirical:**
- **Subtle electronic effects** (e.g., charge delocalization in heterocycles)
- **Quantitative accuracy** for nitrogen-containing groups (larger deviations)
- **Non-adiabatic effects** (if vibronic coupling is critical)

**➡️ Recommendation:**
Start with **GFN2-xTB** or **DFTB3** for screening. Validate a subset with **DFT (e.g., ωB97X-D3, M06-2X)** + a **polarizable continuum model (PCM)** for solvation. If barriers correlate well, proceed with semi-empirical for the full set.

### **🔹 Photoinduced PCET (Optical Excitation)**
**✅ For excited-state barriers:**
- **TDDFT** (with **range-separated hybrids**: CAM-B3LYP, ωB97X-D) works for:
  - Excited-state **geometries** and **free-energy barriers** (validated for ESPT in indigo, etc.)
  - **Avoid pure GGA functionals** (PBE, BLYP) – poor for charge-transfer states
- **Multireference (CASSCF/NEVPT2)** needed for:
  - **Diradical character** (e.g., BLUF photoreceptors, some transition metal complexes)
  - **Conical intersections** or **strong correlation** (e.g., Fe, Cu catalysts)

**✅ Semi-empirical for excited states:**
| Method          | Notes                                                                 |
|-----------------|-----------------------------------------------------------------------|
| **TD-DFTB**     | Exists (PBE-based), but **same issues as TDDFT/GGA**: poor for CT states |
| **LC-TD-DFTB**  | Long-range corrected; better for CT, but **not widely benchmarked for PCET** |
| **ZINDO/S**     | Fast for **excitation energies**, but **not for barriers**; can pair with ML to approach TDDFT accuracy |
| **OM2/MRCI**    | Better for **relative excitation energies**, but limited to small systems |

**⚠️ What you’d miss:**
- **Accurate charge-transfer states** (critical for PCET)
- **Proton transfer coupling** in excited states (often requires **non-adiabatic dynamics**)
- **Conical intersections** (need MR methods)

**➡️ Recommendation:**
For **photoinduced PCET barriers**, use **TDDFT with a range-separated functional** (e.g., CAM-B3LYP) + **DFT for ground-state reference**. If you must use semi-empirical, **LC-TD-DFTB** is the best bet, but **validate against TDDFT first**.

### **🔥 When Do You *Need* Multireference (CASSCF/MRCI)?**
| Scenario                          | DFT OK? | Multireference Needed? | Notes                                  |
|-----------------------------------|---------|------------------------|----------------------------------------|
| **Closed-shell organic PCET**     | ✅ Yes  | ❌ No                  | DFT/GFN2-xTB usually sufficient        |
| **Transition metals (Fe, Cu, Ni)**| ⚠️ Maybe | ✅ **Yes** (often)     | Diradical states, spin crossover       |
| **Strong correlation (e.g., BLUF)**| ❌ No   | ✅ **Yes**             | CASSCF+NEVPT2 benchmark for TDDFT      |
| **Conical intersections**          | ❌ No   | ✅ **Yes**             | MRCI or CASSCF+NEVPT2                  |
| **Nitrogen-heavy heterocycles**    | ✅ Yes  | ❌ No (usually)        | But check with DFT validation           |

### **🚀 High-Throughput Workflow (Your Case)**
1. **Pre-screen with GFN2-xTB or DFTB3**:
   - Compute **ground-state barriers** for all candidates.
   - Use **N–H corrected parameters** (DFTB2-NH, DFTB3-NH) for heterocycles.
   - **Cost**: ~1000x faster than DFT; feasible for **10,000+ molecules**.

2. **Validate with DFT**:
   - Pick **top 10–20 candidates** from semi-empirical screening.
   - Recompute barriers with **ωB97X-D3/def2-TZVP + PCM**.
   - Check **correlation** (R² > 0.9 usually acceptable).

3. **For photoinduced PCET**:
   - **Skip semi-empirical for barriers** (use TDDFT directly).
   - If **absolutely necessary** for speed, use **LC-TD-DFTB** but **validate heavily**.

4. **Avoid**:
   - **Pure GGA TDDFT** (PBE, BLYP) for PCET.
   - **ZINDO for barriers** (only for excitation energies).
   - **DFTB without SCC** (non-SCC is inaccurate for barriers).

### **📌 Summary Table: Method vs. Use Case**
| **Goal**                          | **Best Method**               | **High-Throughput Alternative** | **What’s Missing**                     |
|-----------------------------------|-------------------------------|--------------------------------|----------------------------------------|
| **Ground-state PCET barriers**    | DFT (ωB97X-D3)                | **GFN2-xTB** or **DFTB3**      | Subtle electronic effects (~2–3 kcal/mol error) |
| **Photoinduced PCET barriers**    | TDDFT (CAM-B3LYP)             | LC-TD-DFTB (with caution)      | Charge-transfer accuracy, non-adiabatic effects |
| **Strong correlation (TM, diradical)** | CASSCF+NEVPT2          | ❌ None                        | Semi-empirical fails here               |
| **Excitation energies only**      | TDDFT (range-separated)      | **ZINDO/S** or **LC-TD-DFTB**  | Barriers still need TDDFT/DFT          |

### **🔬 Key References**
- **DFT as workhorse for PCET**: [PMC10416817](https://pmc.ncbi.nlm.nih.gov/articles/PMC10416817/) (Hammes-Schiffer group)
- **Semi-empirical benchmarks**: [JCTC 2019](https://pubs.acs.org/doi/10.1021/acs.jctc.8b01176) (GFN2-xTB barriers), [JCTC 2025](https://pubs.acs.org/doi/10.1021/acs.jctc.5c00690) (DFTB/GFN2 for biochemical PT)
- **Photoinduced PCET**: [JACS 2015](https://pubs.acs.org/doi/10.1021/jacs.5b04087) (TDDFT challenges), [PubMed 2019](https://pubmed.ncbi.nlm.nih.gov/31513399/) (TDDFT for ESPT barriers)
- **TD-DFTB**: [RSC 2020](https://pubs.rsc.org/en/content/articlehtml/2020/cp/c9cp05753f) (LC-TD-DFTB benchmark)

### **⚡ Final Answer**
**For your high-throughput screening of ground-state PCET barriers in heterocycles:**
✅ **GFN2-xTB or DFTB3** are **good enough** to rank candidates and estimate barriers (±2–3 kcal/mol).
✅ **Validate with DFT** (ωB97X-D3) for the top hits.
❌ **Avoid DFTB without SCC or pure GGA functionals**.
❌ **No need for CASSCF** unless you have transition metals or diradicals.

**For photoinduced PCET:**
✅ **TDDFT with range-separated functional** (CAM-B3LYP, ωB97X-D) is the **minimum**.
⚠️ **LC-TD-DFTB** can be tried for speed, but **expect limitations for charge-transfer states**.
❌ **ZINDO is not suitable for barriers** (only excitation energies).

**If you need a semi-empirical TD method for PCET:**
- **TD-DFTB exists** (in DFTB+), but **use LC-TD-DFTB** if available.
- **OM2/MRCI** is an alternative for small systems (better for excitations than barriers).

---

# Grok

**For ground-state or field/electron-injection induced PCET (hydrogen/proton transfer coupled to electron transfer or injection) in heterocyclic molecules, normal DFT (especially hybrids or range-separated functionals) is a solid starting point for energy barriers, while DFTB and xTB methods (particularly GFN2-xTB or the newer g-xTB) can be useful for high-throughput screening with caveats.** Multireference methods like CASSCF are generally not required for routine screening but may be needed for validation in cases with strong static correlation.

### Key Considerations for PCET Computations
PCET often involves concerted or stepwise electron/proton movement, open-shell species, charge transfer, and possibly hydrogen tunneling or environmental effects (solvent, electric field). Heterocycles (e.g., with N, O, S) can have delocalized π-systems or tautomerism that add complexity.

- **Normal DFT**: Widely used as the "workhorse" for PCET thermodynamics, kinetics (via transition state searches or metadynamics), and barriers. Use functionals that handle charge transfer and dispersion well (e.g., ωB97X-D, M06-2X, or range-separated hybrids). Include implicit solvent or explicit molecules + QM/MM for realism. Barriers can be reasonable (often within a few kcal/mol of higher-level references after benchmarking), but self-interaction error or delocalization error can affect charge-separated states or barriers.
- **What's often missing in plain DFT**: Accurate treatment of static correlation (if biradicaloid or near-degenerate states), dispersion (use -D corrections), solvent reorganization, nuclear quantum effects (tunneling — add with instanton or path-integral methods), and sometimes basis set superposition error. For electric field effects, apply external fields in the calculation. For electron injection, model charged/radical species carefully (spin contamination, etc.).

**For high-throughput screening of many molecules, semiempirical methods like DFTB or xTB are attractive** because they are orders of magnitude faster than DFT while still capturing essential chemistry.

- **DFTB (e.g., DFTB3)**: Good for proton transfer and some PCET studies, especially with QM/MM or metadynamics for free energy surfaces. It has been used for ground-state PCET free energies. Limitations include approximate electrostatics and poorer performance for some charge-transfer or excited-state properties without extensions (e.g., long-range corrected LC-DFTB).
- **Grimme's xTB methods (GFN2-xTB, etc.)**: Excellent for geometries, conformer sampling (with CREST), and noncovalent interactions. GFN2-xTB performs surprisingly well for some proton-transfer barriers among semiempirical methods. The newer **g-xTB** improves barrier heights significantly (thanks to approximate range-separated exchange) and approaches hybrid DFT quality for many properties while remaining very fast. These are suitable for initial high-throughput screening of barriers and structures, followed by DFT refinement on promising candidates.
  - **Limitations (what's missing)**: Barriers can still be underestimated (especially in older GFN variants); reaction energies/thermochemistry are not as accurate as DFT for covalent changes; limited for strong multireference character or certain transition metals. Validate against DFT or experiment for your specific heterocycles. Dispersion and hydrogen bonding are well-handled in recent versions.

**Multireference methods (CASSCF, CASPT2, etc.)**: These are important if there's significant static correlation (e.g., biradicals, avoided crossings, or strong mixing in transition states), which can occur in some PCET pathways. However, they are computationally expensive and not practical for high-throughput screening of *many* molecules. Use them for benchmarking a subset or detailed mechanistic study on key systems, often with active space selection focused on π-orbitals or reacting centers.

### For Optically Excited Proton Transfer
You correctly note that **TDDFT** (or equivalents) is typically needed for photoinduced processes to access excited-state surfaces, conical intersections, or excited-state barriers. Standard TDDFT has limitations for charge-transfer states (use range-separated or tuned functionals) and double excitations.

For **high-throughput screening**, semiempirical excited-state methods are promising:
- **TD-DFTB / LC-TD-DFTB**: Available and much faster than TDDFT. Useful for excited-state properties in large systems or with QM/MM. Performance is reasonable but can have issues with color tuning or response to fields in some cases (e.g., retinal proteins).
- **sTDA-xTB or sTD-DFT-xTB** (simplified Tamm-Dancoff approximation with xTB): Designed exactly for ultra-fast computation of electronic spectra and excited states on large numbers of molecules. Benchmarks show good utility for high-throughput screening (e.g., for TADF emitters or similar photochemistry). These are excellent for initial screening of excitation energies and trends.
- **ZINDO**: Classic semiempirical for excited states/spectra, fast and historically used for organics. It can provide reasonable trends but is older and generally outperformed by modern xTB-based methods for accuracy and breadth.

**Workflow suggestion for high-throughput**:
1. Use GFN2-xTB or g-xTB + CREST for geometries, conformers, and initial ground-state reaction paths/barriers (electric field or charged states).
2. Refine barriers/energies with DFT (e.g., ωB97X-D/def2-TZVP) on top hits.
3. For photoexcitation: Screen excitations with sTDA-xTB or TD-DFTB, then TDDFT on candidates. Explore excited-state surfaces as needed (e.g., via surface hopping or metadynamics).
4. Validate key systems with higher levels (CASPT2, coupled-cluster if feasible) or experiment.

Software: ORCA, DFTB+, xtb (standalone), Gaussian, etc., support these methods. For PCET rates, specialized theories (e.g., from Hammes-Schiffer group) combine quantum treatment of proton/electron with classical environment.

Overall, **xTB/DFTB + selective DFT refinement strikes a good balance for your screening goals**. Pure semiempirical won't replace DFT entirely for quantitative barriers but can efficiently filter thousands of molecules. Always benchmark on a few known systems from your heterocyclic family.

---

# USER

I should clarify: I definitely don't want to run molecular dynamics and wait until the proton hops. I want to sample the path, and also compute electron-phonon (vibronic) coupling, like Frank-condon factor Huangh-rhys factor etc. Do I need CASCCF or TDDFT for that? How can I include my excited (or charged) state into this calculation? I would like to do it in some simple and computationaly efficient way. Constrained-DFT?
We should clarify the question before choosing the method. I want more or less mainly the reaction yield (probability that injection of electron or excitation induce proton transfer along selected reaction coordinate). I don't want so much absolute numbers but rather relative trends which molecules are more or less suitable. This will depend both on barrier and on forces in excited state (slope of excited PES along the reaction coordinate). Some molecules would just suck hydrogen from the other even in ground state (due to acidity\basicity for hetero pairs), some need some impulse. I want molecular pairs which are in sweet spot the reaction should not happen spontaneously in ground state but the activation barrier should be low resp yield of inducing the reaction by decent excitation (electron\hole injection or optically) should be high.

---

# Gemini

Now that the exact goal is clear—**high-throughput relative trends in reaction yields** driven by a screening of forces, potential energy surface (PES) slopes, and vibronic (electron-phonon) couplings—the scope changes significantly.

You absolutely do **not** want Molecular Dynamics (MD) or multi-reference CASSCF. CASSCF would completely kill any high-throughput workflow, and MD is too slow for screening statistical hopping rates.

Instead, the standard formalisms for this are the **Franck-Condon (FC)** or **Herzberg-Teller (HT)** approximations, or a displaced harmonic oscillator model to compute the **Huang-Rhys parameters ($S_i$)**. This requires calculating the geometries, frequencies, and normal modes of both the initial state and the final (product) state.

Here is how you can achieve this computationally with maximum efficiency.

## 1. Electron/Hole Injection (Charged Ground State)

When the reaction is driven by charge injection, everything remains on a *ground-state* PES—just a charged one (anion or cation).

### The Method: Constrained DFT (C-DFT)

**Constrained DFT** is the perfect tool for your screening setup.

* **Why it works:** If you have a molecular pair (Donor-Acceptor), a standard DFT optimization of the charged state might artificially delocalize the injected charge or trigger a spontaneous proton transfer before you can sample the path. C-DFT lets you enforce a specific charge localization (e.g., forcing the injected electron to sit entirely on the Donor heterocycle).
* **Extracting the Yield Trends:** You optimize the initial charged state using C-DFT, and you calculate the forces/slope pointing toward the proton transfer coordinate. You can map out a quick diabatic potential energy curve by stepping the proton.
* **Software:** Packages like **Q-Chem**, **NWChem**, and **CP2K** have native, fast C-DFT implementations.

### The Semiemperical Fast Track: Constrained DFTB

If you want to scale this to thousands of molecules, look at **Constrained DFTB (C-DFTB)**, implemented beautifully in **DFTB+**. You can constrain the population of specific atomic orbitals or fragments to simulate the localized injection. It gives you the geometry, the frequencies, and the initial slope of the charged state at a fraction of DFT's cost.

## 2. Optical Excitation (Excited State)

If the reaction is induced by a photon, you need the properties of the excited state ($S_1$).

### The Method: Linear Response TD-DFTB

For high-throughput screening of Franck-Condon factors and Huang-Rhys parameters in excited states, **TD-DFTB** is your best option.

* To compute vibronic coupling and Huang-Rhys factors, you need the excited-state equilibrium geometry ($R_e^*$) or at least the analytical gradients (forces) at the ground-state geometry ($R_g$).
* **DFTB+** and **AMS** support analytical excited-state gradients for TD-DFTB.
* You can extract the excited-state forces directly at the Franck-Condon geometry. The projection of these forces onto the ground-state normal modes gives you the **linear electron-phonon coupling constants**, from which you directly get the Huang-Rhys factors ($S_i = \frac{\omega_i \Delta q_i^2}{2\hbar}$).

### What about ZINDO?

Skip ZINDO. While it can give you a vertical excitation energy fast, it does not support the analytical excited-state gradients or normal mode projections needed to easily get vibronic couplings or PES slopes.

## 3. High-Throughput Screening Workflow

To screen for the "sweet spot" (stable in ground state, but high yield upon injection/excitation), you can build an automated python pipeline using a tight-binding framework:

```
               [ Step 1: Ground State Screening ]
              Optimize neutral pairs using GFN2-xTB
             Filter out pairs that spontaneously transfer
                                │
                                ▼
               [ Step 2: Path & Force Sampling ]
             /                                 \
  (Charge Injection)                      (Optical Excitation)
 Run C-DFTB on charged state              Run TD-DFTB on S1 state
  Evaluate initial gradient                Evaluate initial gradient
             \                                 /
                                │
                                ▼
               [ Step 3: Vibronic Fingerprint ]
             Project gradients onto normal modes (Duschinsky)
             Calculate Huang-Rhys (S) and Franck-Condon factors
                                │
                                ▼
               [ Step 4: Final Selection (The Sweet Spot) ]
            High S along N-H/O-H stretch + Low barrier = High Yield

```

### Finding the "Sweet Spot" using Descriptors

Instead of computing full multi-dimensional Franck-Condon overlap integrals for thousands of pairs, you can rank your molecules using two highly efficient semiempirical descriptors:

1. **The Driving Force Slope ($\frac{\partial E}{\partial R}$):** Calculate the gradient of the excited/charged state at the ground-state equilibrium geometry, specifically projected onto the proton-transfer coordinate vector. If the slope is steep toward the acceptor, the wavepacket will quickly accelerate toward transfer.
2. **The Huang-Rhys Factor ($S_i$) of the Proton-Stretch Mode:** Look at the $S_i$ value specifically for the $N-H$ or $O-H$ stretching vibration (usually around $3000\text{ cm}^{-1}$). A high $S_i$ for this mode means the electronic transition strongly couples to the proton's motion, indicating a high probability of a vibronically mediated hop.

By utilizing **C-DFTB** for injection and **TD-DFTB** for optical paths, you can screen these two descriptors for thousands of heterocyclic pairs in days rather than months.

---

# Chat GPT 5.5

Yes — your target is not “MD proton hops”, but a **photo/electron-triggered reaction-coordinate branching problem**.

For screening, I would reduce it to two PESs along one coordinate:

[
q = r_{\mathrm{X-H}} - r_{\mathrm{Y-H}}
]

Ground state:

[
E_0(q)
]

Triggered state: charged or excited:

[
E_*(q)
]

Then rank molecules by:

[
\Delta E^\ddagger_0,\quad
\Delta E^\ddagger_*,\quad
F_*=-\frac{dE_*}{dq},\quad
\Delta q_* ,\quad S=\frac{\omega}{2\hbar}(\Delta q)^2
]

where (S) is essentially the Huang–Rhys / Franck–Condon displacement measure.

## For electron or hole injection

You probably **do not need TDDFT**.

Use:

[
E_N(q),\quad E_{N+1}(q),\quad E_{N-1}(q)
]

That is: neutral, anion, cation PESs along the proton-transfer coordinate.

This directly tells you whether electron/hole injection pushes the proton:

[
F_{\mathrm{inj}}(q)
===================

-\frac{d}{dq}
\left[
E_{N\pm1}(q)-E_N(q)
\right]
]

For cheap screening:

1. optimize ground-state pair;
2. scan constrained proton coordinate (q);
3. calculate neutral + charged single-points at each (q);
4. compute slopes and barriers;
5. optionally relax all non-(q) coordinates at each point.

This can be done with **GFN2-xTB / g-xTB** very efficiently. For the top candidates, repeat with DFT.

CDFT becomes useful if the injected electron/hole must be localized on a chosen molecule. Ordinary anion/cation calculations may delocalize the charge artificially. CDFT can construct localized charge-transfer states and charge-localized diabatic surfaces; CP2K has CDFT machinery for this kind of charge-transfer problem. ([CP2K Manual][1])

So for electron injection:

[
E_{\mathrm{e\ on\ A}}(q),\quad
E_{\mathrm{e\ on\ B}}(q)
]

via CDFT is often more meaningful than just “total anion”.

## For optical excitation

Here you need an excited-state PES:

[
E_{S_1}(q)
]

For screening, I would not jump to CASSCF. Use:

* **sTDA-xTB / sTD-xTB** for ultrafast excited-state trends;
* **TD-DFTB / TD-LC-DFTB** as a better semiempirical excited-state PES method;
* **TDDFT/TDA** for validation.

DFTB+ supports linear-response TD-DFTB recipes, and recent DFTB+ versions include TD-DFTB and TD-LC-DFTB/TDA implementations. ([DFTB+ Recipes][2]) Grimme’s sTDA-xTB workflow computes excited states from an xTB ground-state wavefunction and is explicitly intended for fast spectra/excited-state screening. ([chemie][3])

## Do you need CASSCF?

Mostly **no**, unless the reaction coordinate crosses into:

* diradical character,
* conical intersection region,
* strong charge-transfer/open-shell mixing,
* bond-breaking excited state with two comparable configurations,
* proton transfer coupled to aromaticity switching with near-degenerate Kekulé states.

For high-throughput ranking, CASSCF is too expensive and too delicate. Use it only as a diagnostic on suspicious/top cases.

## Minimal model I would use

For each molecule pair, compute:

[
E_0(q)
]

[
E_\mathrm{anion}(q),\quad E_\mathrm{cation}(q)
]

and optionally:

[
E_{S_1}(q)
]

Then define screening descriptors:

[
B_0 = E_0(q^\ddagger)-E_0(q_\mathrm{min})
]

ground-state stability: high enough that proton does **not** transfer spontaneously.

[
B_* = E_*(q^\ddagger)-E_*(q_\mathrm{FC})
]

triggered barrier after excitation/injection.

[
F_* = -\left.\frac{dE_*}{dq}\right|*{q*\mathrm{FC}}
]

initial “kick” along proton-transfer coordinate.

[
\lambda_q = E_*(q_0)-E_*(q_*^\mathrm{min})
]

relaxation energy along the proton coordinate.

[
S_q \approx \frac{\lambda_q}{\hbar\omega_q}
]

Huang–Rhys factor projected onto the PT coordinate.

Sweet spot:

[
B_0 > kT \text{ or experimentally stable}
]

but

[
B_* \lesssim 0.1\text{–}0.3\ \mathrm{eV}
]

and large positive (F_*) toward proton transfer.

## Very efficient workflow

Use xTB/g-xTB as generator:

1. Build H-bonded pair.
2. Define (q=r_{D-H}-r_{A-H}).
3. Constrained scan (q), relaxing all other coordinates.
4. Compute neutral, anion, cation energies at each geometry.
5. For optical candidates, compute sTDA-xTB or TD-DFTB excitation energy at each (q).
6. Fit 1D diabatic/adiabatic curves.
7. Rank by (B_0), (B_*), slope, displacement, Huang–Rhys factor.
8. Recompute top candidates with DFT/TDDFT.

This gives you the thing you actually want: **not absolute kinetics**, but a relative “photo/electron-induced proton-transfer yield proxy”.

My strongest recommendation: start with **charged-state xTB scans + DFT recalibration**, and only add TDDFT/TD-DFTB for cases where optical excitation is truly the trigger.

[1]: https://manual.cp2k.org/trunk/methods/dft/constrained.html?utm_source=chatgpt.com "Constrained DFT"
[2]: https://dftbplus-recipes.readthedocs.io/en/latest/linresp/index.html?utm_source=chatgpt.com "Linear response excitations - DFTB+ recipes - Read the Docs"
[3]: https://www.chemie.uni-bonn.de/grimme/de/software/stda/stda_manual.pdf/%40%40download/file/stda_manual.pdf?utm_source=chatgpt.com "sTDA - User Manual - Chemie@uni-bonn.de"


---

# DeepSeek-V4-pro

Your clarification helps immensely. You want to **rank** heterocyclic pairs by their propensity for electric‑field‑ or excitation‑induced PCET, without doing explicit dynamics. The key quantity is the **yield**—i.e., the probability that an injected charge or photoexcitation triggers proton transfer before the system decays back. This depends on both the barrier in the relevant electronic state and the slope of that state’s potential energy surface (PES) along the proton coordinate (which sets the initial force and, via displacement, the vibronic coupling). You want a fast, semiempirical‑first approach that can still give you the necessary vibronic ingredients (Franck–Condon factors, Huang–Rhys factors).

Below I first clarify which methods are needed (CASSCF is almost certainly **not**), then outline how to calculate the yields simply and efficiently, including the use of constrained‑DFT (probably not needed) and semiempirical excited‑state methods.

### 1. Do you need CASSCF, TDDFT, or something else?

**Short answer:**  
- **CASSCF** – no, unless your molecules have genuine diradical character (unlikely for simple heterocyclic pairs).  
- **Electron/hole injection** (charged state) – standard DFT for the radical ion is enough.  
- **Optical excitation** – you need an excited‑state method; for screening, **sTDA‑xTB** (or TD‑DFTB) is the ideal semiempirical choice, and TDDFT can be used for final validation.

**Why not CASSCF?**  
Proton transfer between closed‑shell heterocycles rarely involves near‑degeneracies that would require multireference methods. Even after electron injection or excitation, the radical or excited state usually retains dominant single‑configuration character. You can check a T1 diagnostic from a quick DFT calculation to be safe, but for high‑throughput you can assume CASSCF is unnecessary.

**What about constrained‑DFT (CDFT)?**  
CDFT is used to **localise a charge** on a specific fragment, creating a diabatic state for electron transfer. In PCET, if you want to compute the *electronic coupling* between a reactant and product diabatic state (e.g., “charge on A + proton on B” vs “charge on B + proton on A”), CDFT can be helpful. However, for a first‑pass screening where you only need trends in barriers and slopes, you can work entirely with **adiabatic** PES scans—no need for CDFT. If later you require nonadiabatic rate constants, you can add a diabatisation step (e.g., GMH or CDFT), but it’s not essential for the relative yields you seek.

### 2. Computing the reaction yield trends – a simple picture

The yield of induced PT is governed by a competition between the proton‑transfer rate \(k_{\text{PT}}\) in the excited/charged state and the lifetime \(\tau\) of that state (radiative + non‑radiative decay). High yield means \(k_{\text{PT}} \gg 1/\tau\).

For a given PES, \(k_{\text{PT}}\) can be estimated from:
- an adiabatic barrier height \(\Delta E^\ddagger\) (with nuclear quantum corrections) and a prefactor, or
- a Marcus‑like PCET model (if the reaction is nonadiabatic) using reorganisation energy and driving force.

Because you want **relative trends**, ranking molecules by a simple **descriptor** is often sufficient:

**Descriptor = (Force on the proton in the initial state) × (exothermicity) / (some penalty for too high ground‑state barrier)**

Concretely, you can compute:
1. **Ground‑state (neutral) PES** along the proton coordinate. You want a barrier \(\Delta G^\ddagger_{\text{GS}} > 0\) (no spontaneous transfer), but not huge (say > 0.5 eV might make the pair uninteresting).
2. **Charged/excited‑state PES** from the same starting geometry (the vertically accessed state). The slope \(\frac{dE}{dx}\) at the Franck–Condon point gives the initial acceleration of the proton. A steeper downhill slope → faster motion.
3. The **exothermicity** \(\Delta E\) (energy difference between the initial and final proton positions on that state) – a large driving force helps overcome any residual barrier.
4. The **Huang–Rhys factor** \(S\) for the proton mode, which is simply \(S = \frac{\omega}{2\hbar} \Delta x^2\) (where \(\Delta x\) is the equilibrium displacement along the mode). A large \(S\) means strong vibronic coupling and favourable Franck–Condon factors for the transition, which can enhance the PT rate.

These quantities can be obtained from 1D or 2D PES scans and are perfectly accessible with fast methods.

### 3. Efficient workflow for high‑throughput screening

Here is a step‑by‑step protocol that balances speed with reasonable physics:

#### Step 1: Prepare geometries with GFN2‑xTB
- For each heterocyclic pair (A–H…B), generate a starting hydrogen‑bonded complex.
- Run a relaxed scan along the proton transfer coordinate (e.g., the O–H or N–H distance, or a linear combination) using GFN2‑xTB. This gives you a **ground‑state neutral PES**.
- Identify the minimum (reactant), product minimum, and the TS barrier \(\Delta E^\ddagger_{\text{GS}}\). Filter out pairs that are either already barrierless (spontaneous) or have a barrier > ~0.6 eV (too slow).

#### Step 2a: Charged‑state PES (electron/hole injection)
- For the **radical anion** (electron injected) or **radical cation** (hole injected), perform the same PES scan with **unrestricted DFT** (or unrestricted GFN2‑xTB for even faster pre‑screening, using the `--uhf` flag in `xtb` and setting charge -1 or +1).
- Extract the slope at the neutral ground‑state geometry (vertical point) and the exothermicity. The barrier in the charged state might be reduced or even inverted.

#### Step 2b: Excited‑state PES (optical excitation)
- Use **sTDA‑xTB** (`xtb --gfn2 --tda`) to compute vertical excitation energies and, importantly, **excited‑state gradients** (via finite differences). This is available in the `xtb` code by requesting gradients on the TDA state.
- Scan the same proton coordinate on the lowest bright (or reactive) excited state. sTDA‑xTB is fast enough (seconds per gradient) to scan dozens of points per molecule.
- Again, extract the slope at the Franck‑Condon point, the barrier (if any), and the driving force.

#### Step 3: Compute vibronic descriptors
- **Huang–Rhys factor**: from the excited‑state scan, find the equilibrium proton position on that state (\(x_{\text{eq}}^*\)). The shift \(\Delta x\) relative to the ground‑state equilibrium. The effective frequency \(\omega\) you can get from a harmonic fit to the ground‑state PES near the minimum. Then \(S = \frac{\omega \Delta x^2}{2\hbar}\). A larger \(S\) means stronger coupling of the proton mode to the electronic transition.
- **Franck–Condon factors**: if you later want to compute nonadiabatic PCET rates, you can build 1D proton potentials and solve for vibrational wavefunctions. But for screening, \(S\) and the slope already contain the key information.

#### Step 4: Ranking descriptor
Combine the quantities into a simple figure of merit, for example:

\[
\text{Score} = \frac{|\text{slope}_{\text{exc/charged}}| \times |\Delta E|}{\Delta E^\ddagger_{\text{GS}} + \epsilon}
\]

where \(\epsilon\) prevents division by zero. This favours pairs with a steep downhill initial force, large exothermicity, and a ground‑state barrier that is small but non‑zero. You can adjust the functional form based on chemical intuition.

#### Step 5: Validate a handful of top candidates with DFT/TDDFT
For the most promising pairs, re‑compute the PES scans with:
- **ωB97X‑D3/def2‑SVP** (or at least a range‑separated hybrid) for neutral and charged states.
- **TD‑ωB97X‑D3/def2‑SVP** for the excited state.
This will ensure the trends from semiempirical methods are reliable.

### 4. What about “constrained‑DFT”?

CDFT would be useful if you needed to separate the electron and proton transfer into diabatic states (e.g., to compute the electron‑proton correlation). In your case, the adiabatic PES scan already contains the mixed electronic character, and you are looking for a **yield trend**, not an absolute nonadiabatic rate. The slope and barrier on the adiabatic surface are adequate to rank pairs. Therefore, I recommend **against** CDFT for initial screening—it adds complexity without changing the ranking.

### 5. Semiempirical tools you can use right now

- **xTB** (GFN2‑xTB + sTDA):  
  - Ground‑state scans, charged‑state scans (UHF‑xTB), and TDA excited‑state gradients.  
  - Extremely fast; ideal for screening thousands of pairs.  
- **DFTB+** with TD‑DFTB:  
  - Also provides analytic excited‑state gradients, but parametrisation may be more cumbersome for arbitrary heterocycles. sTDA‑xTB is simpler to deploy.  
- **ZINDO/S**:  
  - Available in ORCA, but less accurate for PES scans than sTDA‑xTB. Not recommended.

All of these can handle electric fields (keyword `EFIELD` in xTB) if you want to mimic the effect of a local field in a junction.

### Summary

- You do **not** need CASSCF.  
- For charged states, regular unrestricted DFT (or UHF‑xTB) suffices.  
- For excited states, use **sTDA‑xTB** for high‑throughput scans; it gives you slopes, barriers, and Huang–Rhys factors.  
- Construct a simple score that captures the “sweet spot” (no spontaneous ground‑state transfer, but large driving force/low barrier in the active state).  
- Constrained‑DFT is an unnecessary complication for your current goal.

This approach will let you rapidly filter molecular pairs based on their induced PCET potential, using only a few minutes of computer time per pair. Let me know if you need more detail on the practical implementation of sTDA‑xTB excited‑state scans or the Huang–Rhys calculation.

---

# Kimi 2.6

This is a very well-defined problem. Let me break down what you need and identify the most efficient path.

## What You Actually Need to Compute

For each molecular pair, you need:

1. **Ground state PES** along the proton transfer coordinate (N-H or O-H distance)
2. **Excited/charged state PES** along the same coordinate  
3. **Electronic coupling** between initial and final states (for non-adiabatic rates)
4. **Vibronic overlap** (Franck-Condon factors, Huang-Rhys) for optical excitation cases
5. **Reaction yield** = f(barrier, driving force, reorganization energy, coupling)

The "sweet spot" you describe is: ΔG° ≈ 0 to slightly uphill in ground state, but photoinduced/charge-injected state makes it downhill with low barrier.

## Do You Need CASSCF or TDDFT?

**For the PES shapes and barriers: No, not necessarily.**

**For vibronic coupling and non-adiabatic rates: It depends on the electronic structure at the crossing.**

Let me be specific about what breaks single-reference methods:

| Situation | Single-reference OK? | What to use |
|-----------|---------------------|-------------|
| Proton transfer between closed-shell heterocycles (pyridine-pyrrole, etc.) | Usually yes | DFT or even DFTB/xTB |
| Involves radical cation/anions (electron/hole injection) | Often yes, but check | UKS-DFT, constrained DFT |
| Concerted PCET with significant H-bonding | Yes with dispersion | DFT-D3, xTB |
| States with near-degeneracy, bond homolysis, or strong diradical character | No | CASSCF or multireference |
| Charge-transfer excited states in large π-systems | TDDFT often fails | ADC(2), sTDA-xTB, or range-separated TDDFT |

For heterocyclic pairs doing PT (not H-atom transfer), **you are mostly in the "usually yes" category**.

## The Efficient Approach: Constrained DFT + FOB-SH or Landau-Zener

Given your goals (relative trends, not absolute numbers, high-throughput), here's a practical workflow:

### Step 1: Ground and Charged State PES with Constrained DFT

**Constrained DFT (CDFT)** is exactly what you want for this. It allows you to:
- Define diabatic states (e.g., "proton on donor" vs "proton on acceptor")
- Compute electronic coupling between these diabats as the off-diagonal element
- Get proper avoided crossing behavior

**Implementation:**
- **Q-Chem** has built-in CDFT with coupling calculations
- **PyCDFT** (python interface) 
- **ORCA** has some constrained SCF capabilities

For high-throughput, you can script this: constrain the proton coordinate, optimize other degrees of freedom, scan the coordinate.

**Computational cost:** ~2-3× a normal DFT calculation per point. For a 20-point scan with 50 pairs, this is very manageable.

### Step 2: Excited State PES

For optical excitation:

- **sTDA-xTB** for initial screening (fast, gives you vertical excitation and excited state gradients)
- **TD-DFT with range-separated hybrid** (ωB97X-D, CAM-B3LYP) for validation on subset
- **Linear-response TDDFT** gives you excited state forces analytically — you can do relaxed scans

**Key point:** You don't need full TDDFT dynamics. You need:
- Vertical excitation energy at ground state geometry
- Excited state energy at displaced geometries along PT coordinate
- This gives you the slope of the excited PES (the "impulse" you mentioned)

### Step 3: Vibronic Coupling Without Full CASSCF

You want Franck-Condon factors and Huang-Rhys parameters. Here's how to get them efficiently:

**For electron/hole injection (charged states):**
- Compute **reorganization energy λ** from the PES curvature: λ = E(optimized neutral at charged geometry) - E(optimized charged)
- Huang-Rhys S = λ / ℏω (where ω is the PT mode frequency)
- This is a **harmonic approximation** using your DFT/CDFT PES. No CASSCF needed.

**For optical excitation:**
- **Vertical gradient (VG) approximation** or **linear coupling model**: Use ground state and excited state PES curvatures from TDDFT
- **ezFCF** or **FCclasses** can compute FC integrals from DFT frequencies and displacements
- **Vibronic coupling in harmonic approximation** is sufficient for relative trends

**If you want non-adiabatic coupling elements** (for Landau-Zener or Marcus-type rates):
- **CDFT directly gives you H₁₂** (electronic coupling)
- **FMO-DFT** or **fragment orbital DFT** approaches also work
- For TDDFT: **NACME** (non-adiabatic coupling matrix elements) can be computed analytically in some codes (Q-Chem, Gaussian)

### Step 4: Rate and Yield Models

You don't need dynamics. Use analytical rate theories:

**For electron/hole injection induced PT:**
- **Marcus theory** or **Marcus-Levich-Jortner** (if high-frequency quantum modes involved):
  k = (2π/ℏ) |H₁₂|² (1/√(4πλkT)) exp(-(ΔG° + λ)² / 4λkT)
- Or **Landau-Zener** for the crossing probability if you have velocity information

**For optical excitation:**
- **Kasha-Huang-Rhys model**: Yield depends on overlap of vibrational wavefunctions
- **Sum-over-states** or **generating function** approach for FC integrals

**For relative trends**, you can even simplify further:
- Compare (ΔG* + λ)² / 4λ across molecules (Marcus activation)
- Compare excited state slopes (∂E_excited/∂q) at ground state minimum

## Specific Recommendation for Your Workflow

### Tier 1: Ultra-fast screening (1000s of pairs)

Use **GFN2-xTB** for:
- Ground state geometry optimization
- Proton transfer coordinate definition
- Approximate PES scan (constrain N-H or O-H distance, relax rest)

Use **sTDA-xTB** for:
- Excited state energies at key geometries
- Quick check if excited state is PT-active (does S₁ slope favor product?)

**Filter:** Keep only pairs where:
- Ground state barrier > 5 kcal/mol (doesn't happen spontaneously)
- Excited state has negative slope or significantly reduced barrier

### Tier 2: Quantitative screening (100s of pairs)

Use **CDFT** (B3LYP-D3/def2-SVP or ωB97X-D/def2-SVP):
- Scan proton coordinate with constraint
- Compute electronic coupling H₁₂ between diabats
- Get reorganization energy λ from PES
- Compute Marcus rate or Landau-Zener probability

Use **TD-DFT** (same functional) for optical cases:
- Adiabatic excited state PES scan (TDDFT relaxed)
- Extract excited state force constants and displacements
- Compute FC factors with ezFCF or in-house script

### Tier 3: Validation (10s of pairs)

- Compare CDFT barriers to **DLPNO-CCSD(T)** or **CASPT2** for problematic cases
- Check TDDFT against **ADC(2)** for charge-transfer states
- Compute **exact NACME** if doing full non-adiabatic dynamics

## Do You Ever Need CASSCF?

Only if CDFT diagnostics show:
- Severe spin contamination in UKS (⟨S²⟩ >> 0.75 for doublets)
- Orbital instability (multiple SCF solutions with similar energy)
- Bond-breaking region where DFT predicts artificial symmetry breaking

For heterocyclic PT, this is rare. **Test on 2-3 representative systems first.**

## Practical Implementation Sketch

```python
# Pseudo-workflow for one pair
for pair in database:
    # 1. Optimize ground state geometries (reactant, product, TS guess)
    # 2. Constrained scan: d(N-H) from 1.0 to 2.0 Å
    #    - Ground state DFT energy
    #    - Charged state DFT energy (if electron injection)
    #    - S1 TDDFT energy (if optical)
    # 3. Fit PES to polynomial, extract barrier and curvature
    # 4. CDFT: compute H12 at crossing geometry
    # 5. Compute λ from Marcus parabola fit
    # 6. Rate = f(H12, λ, ΔG°)
    # 7. Yield = rate / (rate + k_decay)  # competing processes
```

## Summary

| What you need | Simplest adequate method | When to upgrade |
|--------------|------------------------|-----------------|
| Ground state PES/barrier | GFN2-xTB → CDFT-DFT | If strong H-bonding or charge delocalization |
| Charged state PES | CDFT-DFT (UKS) | If spin contamination or orbital instability |
| Excited state PES | sTDA-xTB → TD-DFT | If CT states or large π-systems |
| Electronic coupling | CDFT H₁₂ | If non-Condon effects important |
| Vibronic coupling (FC, HR) | Harmonic approx from DFT PES | If strong anharmonicity or Duschinsky rotation |
| Reaction yield | Marcus/LZ rates | If need explicit dynamics or quantum coherence |

**Bottom line:** For your specific goal (relative trends, sweet spot identification), **CDFT + harmonic vibronic coupling + Marcus/Landau-Zener theory** is the sweet spot of accuracy vs. cost. You likely don't need CASSCF for heterocyclic PT unless your diagnostics fail. Start with xTB for filtering, validate with CDFT/TDDFT on the promising subset.

Would you like me to elaborate on the CDFT implementation details or the specific rate expressions for your electron-injection vs. optical excitation cases?

---

# Mistral

Here’s a **practical, computationally efficient workflow** tailored to your goals: **screening molecule pairs for PCET yield trends** (not absolute rates) based on **barriers + excited-state forces**, without MD.

### **🎯 Your Core Requirements**
| Goal | What You Need | Computationally Cheap? |
|------|---------------|------------------------|
| **Reaction yield proxy** | Barrier height (ΔG‡) + slope of excited PES along RC | ✅ Yes (constrained optimizations) |
| **Vibronic coupling** | Frank-Condon (FC) / Huang-Rhys (S) factors | ✅ Yes (geometry displacements) |
| **Excited/charged states** | PES of S₁, cation/anion states along RC | ⚠️ Semi-empirical OK for screening |
| **Sweet spot** | ΔG_ground > 0 (no spontaneous PT), ΔG_excited < 0 or low ΔG‡_excited | ✅ Yes (energy comparisons) |

**Key insight**: For **relative trends**, you only need **ΔG, λ (reorganization energy), and PES slopes**—not full dynamics or high-level vibronic coupling.

### **🔧 Method Choice: What You *Actually* Need**
| Scenario | **Minimum Viable Method** | **Why?** | **What’s Missing?** |
|----------|---------------------------|----------|--------------------|
| **Ground-state PES** | **Constrained-DFT** or **constrained-GFN2-xTB** | Maps RC efficiently; no MD | Minor quantitative errors (~2–3 kcal/mol) |
| **Charged states (e†/hole injection)** | **DFT or GFN2-xTB with ±1 charge** | Just optimize the ion; no TDDFT needed! | Same as above |
| **Optically excited states** | **TDDFT (CAM-B3LYP/ωB97X-D)** or **LC-TD-DFTB** | Range-separated functionals handle CT states | Semi-empirical TD may miss fine details |
| **Vibronic coupling (FC/S factors)** | **Normal mode analysis + geometry displacement** | Computes S = ½·m·ω·ΔQ²/ħ from ground/excited geometries | Ignores non-Condon effects (usually fine for screening) |

**❌ You do *not* need:**
- **CASSCF** (unless you have transition metals/diradicals—unlikely for heterocycles).
- **Full non-adiabatic MD** (you’re sampling statically via constrained PES).
- **High-level MRCI** (overkill for trends).

### **⚡ Workflow: High-Throughput Screening**
#### **Step 1: Define Reaction Coordinate (RC)**
- **Proton transfer**: Use `d(O-H) - d(H-N)` (or similar for your heterocycle pair).
- **Collective variable**: Or use a linear combination of bond lengths/angles.

#### **Step 2: Map PES Along RC (No MD!)**
For **each molecule pair** and **each state** (neutral, cation, anion, S₁):
1. **Constrained optimization**:
   - Fix RC at 5–10 points (e.g., proton at donor, midpoint, acceptor).
   - Optimize all other degrees of freedom (GFN2-xTB or DFT).
   - **Cost**: ~100x faster than MD; parallelizable.
2. **Extract**:
   - **ΔG(RC)**: Energy profile along RC.
   - **F(RC) = -∇E(RC)**: Force (slope) at each point.
   - **Transition state (TS)**: Highest point on PES (if any).

#### **Step 3: Compute Key Quantities**
| Quantity | How to Compute | Screening Proxy |
|----------|----------------|------------------|
| **ΔG_ground** | E_products - E_reactants (ground state) | **Must be > 0** (no spontaneous PT) |
| **ΔG_excited** | E_products* - E_reactants* (excited/charged state) | **Must be < 0 or low ΔG‡** (easy PT after excitation) |
| **Reorganization energy (λ)** | λ = E_reactant(geometry_product) - E_reactant | **Smaller λ = higher yield** |
| **Huang-Rhys factor (S)** | S = ½·m·ω·(ΔQ)²/ħ (from normal modes) | **Larger S = stronger coupling** |
| **PES slope at RC=0** | F = -dE/dRC (at reactant geometry) | **Steeper slope = higher yield** |

#### **Step 4: Estimate Relative Yield**
For **non-adiabatic PCET**, the rate (and thus yield) scales as:
```
k ∝ |V|² · exp[-(ΔG + λ)² / (4λk_B T)]
```
For **screening**, assume `|V| ≈ constant` (similar across molecules) and rank by:
```
Yield Proxy = exp[-(ΔG_excited + λ)² / (4λk_B T)] · |F_excited|
```
where:
- `ΔG_excited` = barrier in excited/charged state (0 if exergonic).
- `λ` = reorganization energy (from ground-state PES).
- `F_excited` = slope of excited PES at RC=0 (driving force).

**Sweet spot criteria**:
✅ **ΔG_ground > 0** (no spontaneous PT in ground state)
✅ **ΔG_excited < 0 or ΔG‡_excited < 5 kcal/mol** (easy PT after excitation)
✅ **Large |F_excited|** (strong driving force in excited state)

### **💡 Computational Efficiency Hacks**
| Task | Fast Method | Validation (Optional) |
|------|-------------|-----------------------|
| **Ground-state PES** | **GFN2-xTB** (constrained) | ωB97X-D3/def2-SVP |
| **Charged-state PES** | **GFN2-xTB with ±1 charge** | Same as above |
| **Excited-state PES** | **LC-TD-DFTB** (DFTB+) | CAM-B3LYP/def2-SVP |
| **Normal modes** | **GFN2-xTB Hessian** | Only for top candidates |
| **Vibronic coupling** | **Finite differences (ΔQ from geometries)** | Full FC calculation |

**Tools**:
- **GFN2-xTB**: [xtb program](https://xtb-docs.readthedocs.io/) (supports constrained optimizations).
- **DFTB+**: [dftb.org](https://dftb.org/) (supports LC-TD-DFTB).
- **Constrained DFT**: Most DFT codes (e.g., Gaussian, Orca, Q-Chem).

### **📊 Example: What to Plot for Screening**
For each molecule pair, generate:
1. **Ground-state PES**: Must have a **barrier** (ΔG_ground > 0).
2. **Excited/charged PES**: Must have **no barrier or small barrier** (ΔG_excited ≤ 0).
3. **Slope comparison**: Excited-state force at RC=0 should be **steeper** than ground state.

**Visual red flags**:
❌ Ground-state PES is **barrierless** (spontaneous PT).
❌ Excited-state PES has a **high barrier** (hard to induce PT).
❌ Excited-state slope is **shallow** (weak driving force).

### **⚠️ Pitfalls to Avoid**
1. **Pure GGA functionals (PBE, BLYP)** for excited states → **use range-separated (CAM-B3LYP, ωB97X-D)**.
2. **Non-SCC DFTB** → **always use SCC (DFTB3, GFN2-xTB)** for barriers.
3. **Ignoring charge localization**: For hole/electron injection, check if the **charge stays on the acceptor** (use Mulliken/ESP charges).
4. **Single-point excited states**: **Optimize excited-state geometries** (TDDFT or LC-TD-DFTB) to get correct slopes.

### **🔬 Minimal Test Case**
Try this on **1–2 molecule pairs** first:
1. **Ground state**: Constrained GFN2-xTB PES along RC.
2. **Cation state**: Add +1 charge, repeat constrained PES.
3. **S₁ state**: LC-TD-DFTB PES (if optical excitation matters).
4. **Compute**:
   - ΔG_ground, ΔG_cation, ΔG_S₁
   - λ (from ground-state PES)
   - F_excited (slope at RC=0 for cation/S₁)
5. **Rank by**: `exp[-(ΔG_excited + λ)² / (4λk_B T)] · |F_excited|`

If the **trends match DFT/TDDFT validation**, scale up to your full set.

### **📌 Summary: Your Action Plan**
| Step | Method | Output | Time per Molecule |
|------|--------|--------|-------------------|
| 1. Ground-state PES | Constrained GFN2-xTB | ΔG_ground, λ | ~1 min |
| 2. Charged-state PES | Constrained GFN2-xTB (±1) | ΔG_excited, F_excited | ~1 min |
| 3. Excited-state PES (if optical) | LC-TD-DFTB | ΔG_S₁, F_S₁ | ~5–10 min |
| 4. Rank by yield proxy | `exp[-(ΔG + λ)² / (4λk_B T)] · |F|` | Instant |
| 5. Validate top 5–10 | DFT/TDDFT | Confirm trends | ~1–2 hours |

**Total for 1000 molecules**: ~2–3 days on a modest cluster (parallelizable).

### **🔗 Key References**
- **Constrained DFT for PCET**: [J. Chem. Theory Comput. 2018, 14, 5749](https://doi.org/10.1021/acs.jctc.8b00624)
- **GFN2-xTB for barriers**: [J. Chem. Theory Comput. 2019, 15, 3080](https://doi.org/10.1021/acs.jctc.8b01176)
- **LC-TD-DFTB**: [Phys. Chem. Chem. Phys. 2020, 22, 2008](https://doi.org/10.1039/C9CP05753F)
- **PCET rate theory**: [Chem. Rev. 2014, 114, 4675](https://doi.org/10.1021/cr400484g) (Hammes-Schiffer)

---

# Grok

**For your goals—high-throughput screening of relative trends in reaction yields/probabilities for induced proton transfer (via electron injection/charging or optical excitation) in heterocyclic molecular pairs, focusing on barriers, excited/charged-state PES slopes along a reaction coordinate, and vibronic factors like Huang-Rhys (HR) and Franck-Condon (FC)—you can largely avoid full CASSCF/multireference methods.** These are too expensive for screening many pairs and are better reserved for benchmarking specific cases with suspected strong static correlation (e.g., near-degenerate states or biradicals).

**CASSCF/ multireference is generally not required here.** Standard (or range-separated hybrid) DFT, ΔSCF/ΔDFT, TDDFT (or approximations), and especially semiempirical methods suffice for relative trends. Multireference character, if present, can often be flagged via diagnostics (e.g., spin contamination, natural orbital occupations) and validated on a subset.

### Recommended Efficient Workflow for Screening
Focus on **sampling reaction paths** (e.g., relaxed scans or nudged elastic band (NEB) along a proton-transfer coordinate, possibly with electric field or charge constraints) rather than unrestrained MD. Compute key descriptors: ground-state barrier (should be high enough to prevent spontaneity), excited/charged-state barrier or driving force/slope (ideally downhill or low barrier post-excitation/injection), and vibronic coupling (HR factors for FC overlaps influencing yield).

1. **Ground-State Screening (Acidity/Basicity, Spontaneous Transfer Check)**:
   - Use **GFN2-xTB or g-xTB** (very fast, good for organics/heterocycles, geometries, and barriers). Perform relaxed scans along the H-transfer coordinate for molecular pairs.
   - Refine promising pairs with hybrid DFT (e.g., ωB97X-D or M06-2X with implicit solvent).
   - Identify "sweet spot" candidates: high ground-state barrier but favorable thermodynamics or low barrier upon perturbation.

2. **Charged State / Electron Injection (Constrained-DFT or ΔSCF)**:
   - **Constrained DFT (cDFT)** is excellent here: It enforces charge localization on one molecule (or fragment) to model diabatic states for electron/proton transfer. Great for computing charge-transfer barriers, diabatic PES along the reaction coordinate, and couplings. Implementations in Q-Chem, ORCA, etc.
   - Alternatively, **ΔSCF/ΔDFT** (promoting an electron to a virtual orbital or optimizing charged states) for relaxed charged-state geometries and PES scans. Efficient and handles open-shell species.
   - For fields: Apply external electric field in the calculation.
   - These allow mapping the charged-state PES slope and barrier efficiently.

3. **Optical Excitation / Excited-State PES**:
   - **TDDFT** (or TDA) for vertical excitations and excited-state gradients/forces. Use range-separated hybrids (e.g., ωB97X, CAM-B3LYP) to mitigate charge-transfer issues common in heterocycles.
   - For **PES scans/relaxed paths in excited state**: TDDFT gradients or, for efficiency, **ΔSCF/ΔDFT** (often better for relaxed excited geometries and CT states than linear-response TDDFT).
   - Semiempirical: **sTDA-xTB or sTD-DFT-xTB** for ultra-fast screening of excitations, spectra, and trends across thousands of molecules. Good for initial filtering; combine with GFN2-xTB geometries. **TD-DFTB** is another fast option for excited surfaces.
   - Slopes/driving forces: Compute excited-state forces at Franck-Condon geometry or along the coordinate—the steeper the downhill slope, the higher the probability of prompt transfer.

**For high-throughput**: Start with xTB/sTDA-xTB for geometries + excitations + quick scans on many pairs. Refine top candidates with DFT/cDFT/TDDFT. This captures relative trends in barriers and slopes well.

### Vibronic Coupling (HR Factors, FC Factors)
These quantify how vibrational overlap affects transition probabilities or yields (e.g., in radiationless transitions or PCET rates).

- **Standard way**: Compute HR factors from normal-mode displacements (and frequencies) between initial (e.g., ground/charged) and final (e.g., proton-transferred) optimized geometries: \( S_k = \frac{\omega_k}{2\hbar} (\Delta Q_k)^2 \) per mode \( k \), then FC factors from overlaps (Poisson distribution approximation for displaced oscillators, or full Duschinsky rotation for accuracy).
- **Efficiency**: Use ground/excited/charged optimized geometries from DFTB/xTB or DFT, then vibrational analysis. Force-based approximations (excited-state forces at ground geometry) avoid full excited optimization for screening.
- Semiempirical support: xTB/DFTB frequencies are usable for this; sTDA-xTB etc. for excited-state info. Not as accurate as DFT but fine for trends.
- Integrate into yield estimate: Combine with barrier/slope (e.g., via simplified PCET rate theories or Landau-Zener for nonadiabatic transitions) for a probability proxy. Steep slope + good FC overlap → higher yield.

**What's missing/limitations**:
- Semiempirical (xTB/DFTB): Good geometries and trends, but barriers/energies may need DFT scaling; excited states approximate (esp. CT character).
- TDDFT: Can fail for long-range CT or double excitations; use diagnostics and tuned functionals.
- Solvent/environment: Implicit models (PCM, SMD) or QM/MM for pairs; critical for acidity and reorganization.
- Tunneling: Add approximate corrections (e.g., WKB) if barriers are relevant.
- Full yield: Requires dynamics (e.g., surface hopping) for absolute numbers, but relative trends from static PES + vibronics are sufficient for screening.

**Software**: xtb (standalone for GFN/g-xTB, sTDA), DFTB+, ORCA/Gaussian/Q-Chem (DFT, TDDFT, cDFT, ΔSCF). Automate with Python (ASE, pyscf, etc.) for high-throughput.

This approach is computationally efficient, focuses on relative suitability ("sweet spot" molecules), and directly addresses path sampling, slopes, barriers, and vibronic factors without full dynamics or heavy multireference methods. Benchmark a few known pairs to calibrate.

---

# USER

Can I use cheap DFTB or g-xTB method to scan the PES plot the n+1\n-1 or excited PES estimate of to see how it looks and in which Regime I'm (if I'm in complicated regime where CASSCF\TDDFT is required or simple...).

I know that PES will be quantitatively wrong but the topological features like crossing and conical intersection should be robust even with cheap methods...
How exactly to do that?
What exactly I should look for?

---

# Chat GPT 5.5

Yes — use cheap methods as a **topology/diagnostic microscope**, but do **not trust conical intersections/crossings too literally**. xTB/DFTB can show “this is likely simple vs dangerous”, but true CI topology is method-sensitive.

## Do this

Define one main proton-transfer coordinate:

[
q=r_{D-H}-r_{A-H}
]

For each sampled (q), relax all other coordinates under constraint, then compute several vertical energies on the **same geometry**:

[
E_N(q),\quad E_{N+1}(q),\quad E_{N-1}(q),\quad E_{S_1}(q),\quad E_{S_2}(q)
]

xTB can do fast charged-state geometry/gradient/Hessian-style work; DFTB+ has TD-DFTB linear-response workflows for excited states; sTDA-xTB is also intended for fast excited-state screening from xTB wavefunctions. ([xtb-docs.readthedocs.io][1])

## What to plot

Plot relative curves against (q):

[
E_i(q)-E_N(q_\mathrm{GS})
]

and also plot the **injection/excitation driving energy**:

[
\Delta E_\mathrm{inj}(q)=E_{N\pm1}(q)-E_N(q)
]

[
\Delta E_\mathrm{exc}(q)=E_{S_1}(q)-E_N(q)
]

The most useful diagnostic is not only the barrier, but the **slope at the Franck–Condon geometry**:

[
F_*(q_\mathrm{FC})=-\left.\frac{dE_*}{dq}\right|*{q*\mathrm{FC}}
]

Large force toward proton transfer means excitation/injection immediately pushes the proton.

## What to look for

### Good “sweet spot”

Ground state:

[
E_N(q)
]

has a stable minimum before proton transfer and a moderate barrier.

Triggered state:

[
E_{N+1},\ E_{N-1},\ \text{or } E_{S_1}
]

has lower barrier, downhill slope, or minimum on the transferred-proton side.

This is the ideal regime.

### Bad: spontaneous ground-state transfer

If (E_N(q)) is downhill already, the molecule is too acidic/basic. It may transfer without stimulus.

### Bad: no response

If (E_*(q)) is almost parallel to (E_N(q)), excitation/injection does not couple to proton transfer.

### Interesting but dangerous

If (S_1) and (S_0), or (S_1) and (S_2), approach/cross near the proton-transfer coordinate, you may enter nonadiabatic/conical-intersection physics. Then cheap methods are only warning flags.

### Multireference warning signs

Look for:

* near-degenerate frontier orbitals;
* HOMO/LUMO gap collapsing along (q);
* spin contamination in charged/open-shell state;
* abrupt charge jumps;
* broken-symmetry solutions;
* excited-state root swapping;
* two different electronic states with different charge localization crossing;
* proton-transfer coordinate coupled to Kekulé/aromaticity switching.

If these appear, validate with TDDFT/TDA, spin-flip TDDFT, CDFT, or small active-space CASSCF/NEVPT2 on selected geometries.

## Minimal high-throughput descriptor

For every pair, compute:

[
B_0,\quad B_*,\quad F_*(q_\mathrm{FC}),\quad q_*^\mathrm{min}-q_0,\quad S_q\approx \frac{\lambda_q}{\hbar\omega_q}
]

where (B_0) is ground-state barrier, (B_*) triggered-state barrier, and (S_q) estimates vibronic displacement.

Rank high when:

[
B_0 \text{ high enough for stability}
]

but

[
B_* \text{ small and } F_* \text{ points toward proton transfer.}
]

## Key caution

Topological features are **not always robust** with cheap methods. Minima/barriers are often qualitatively useful. But conical intersections, avoided crossings, charge-transfer character, and root ordering can change qualitatively. Treat xTB/DFTB crossings as **triage signals**, not final evidence.

[1]: https://xtb-docs.readthedocs.io/en/latest/optimization.html?utm_source=chatgpt.com "Geometry Optimization - xtb doc 2023 documentation"

---

# DeepSeek-V4-pro

Absolutely, you can use cheap methods like GFN2‑xTB or DFTB to **map the qualitative PES** and spot whether the system falls into a “simple” regime (single‑reference, adiabatic) or a “complicated” one (multireference, nonadiabatic, conical intersections). The **topology**—well‑separated avoided crossings, true crossings, near‑degeneracies—often survives even with semiempirical approximations, though you must be aware of possible artefacts. Below I outline exactly how to run these scans and what to look for.

## 1. Which cheap methods for which state?

| State | Recommended cheap tool | Notes |
|-------|------------------------|-------|
| **Neutral ground state** | `xtb --gfn2` (RKS) | Closed‑shell; simple scan. |
| **Radical anion (\(n+1\)) / cation (\(n-1\))** | `xtb --gfn2 --uhf` (unrestricted) | Watch spin contamination and spin densities. |
| **Excited states (optical)** | `xtb --gfn2 --tda` (sTDA‑xTB) or `dftb+` with TD‑DFTB | Request multiple roots (e.g., `--tada 5`) to see crossings. |

All of these are fast enough to scan tens of points along a proton‑transfer coordinate for hundreds of pairs.

## 2. How to run the PES scans (practical recipe)

### 2.1. Ground‑state neutral (no surprise, just for reference)
```bash
xtb coord --gfn2 --opt --scan <scan_input>
```
Example `scan.inp` (a simple linear transit):
```
$constrain
   distance: 1, 10, auto
$end
$scan
   step: 0.05
   nstep: 40
$end
```
This will drive the H‑acceptor bond. Extract energies and bond lengths from `xtbscan.log`.

### 2.2. Charged (electron/hole injection) – radical ion scan
For anion (added electron), set charge = -1 and multiplicity = 2:
```bash
xtb coord --gfn2 --uhf --chrg -1 --uhf --scan ...
```
For cation, charge = +1, mult = 2.  
**Important:** In the scan, the unrestricted calculation may break spin symmetry; that’s fine, but monitor \(\langle S^2 \rangle\). The scan log will print `<S**2>` after each SCF. If it deviates far from 0.75 (pure doublet), it hints at spin contamination and possibly multireference character.

### 2.3. Excited‑state PES
sTDA‑xTB can compute vertical excitation energies and, with finite‑difference, gradients to optimise minima. For a PES scan, you can do a series of single‑point TDA calculations at each geometry along a pre‑computed path (e.g., from the ground‑state scan).  

**Scripted approach (bash + xtb):**
1. Generate geometries along the coordinate (e.g., `xyz` files for each point).
2. For each geometry, run:
   ```bash
   xtb coord.xyz --gfn2 --tda --tada 5 > tda.out
   ```
   This will print the first 5 singlet (or triplet) excitation energies.
3. Extract the energies of the ground state (from the last `SCF` energy) and the TDA states.
4. Plot the **adiabatic excited‑state PES** by picking the state that has the right character (often the lowest bright state, but you can follow the one with largest oscillator strength or a specific orbital transition). If two excited states come very close, you can track their crossing.

If you need gradients for a relaxed scan, `xtb` has the `--grad` flag after a TDA calculation, but an easier route is to use **geometric** relaxation on the excited state via an external optimiser coupled with `xtb`. For qualitative inspection, a rigid scan along the ground‑state reaction coordinate is often enough.

## 3. What exactly to look for – signs of “complicated” regime

### 3.1. Near‑degeneracy and (avoided) crossings
- **Plot all low‑lying states** (ground, first few excited) along the reaction coordinate.  
- If two electronic states approach within **< 0.1–0.2 eV** and then repel (avoided crossing) or actually cross (true crossing), you are in a region where the Born–Oppenheimer approximation may break down, and a **multistate** treatment (e.g., TDDFT with state averaging, or CASSCF) might be necessary.  
- In sTDA‑xTB, true crossings are harder to capture because the Tamm‑Dancoff approximation is a single‑reference method; it may give an avoided crossing with an unphysically large gap or even an incorrect state order. Nonetheless, an **approaching** of two states is a red flag.

**Practical test:** If at some point during the proton transfer the gap between the ground and first excited state drops below ~0.5 eV and the nature of the state changes abruptly (e.g., from local to charge‑transfer), the single‑reference picture is suspect.

### 3.2. Radical ions: spin contamination and instability
- Monitor `<S**2>` in UHF‑xTB. If it exceeds ~0.80–0.85, there is significant spin contamination, indicating that a restricted open‑shell (ROKS) or multireference description might be needed.  
- Look at the **spin density plots** (`.spin` file from `xtb` with `--esp`). If the unpaired electron delocalises over both fragments in a way that cannot be described by a single determinant, that’s another warning.  
- Check if the UHF solution has a **lower‑energy broken‑symmetry** alternative; if two different UHF solutions with different spin distributions are close in energy, the system is strongly correlated.

### 3.3. HOMO–LUMO gap closure
- Even from ground‑state RKS‑xTB, monitor the frontier orbital gap along the path. If it narrows to **< 1 eV** (in xTB, gaps are often underestimated anyway, but a trend towards zero is telling), then static correlation becomes important.  
- In charged‑state scans, the SOMO‑LUMO gap or the HOMO‑SOMO gap can vanish, signalling metal‑like electronic structure that definitely needs multireference.

### 3.4. Sudden change in electronic character
- **Dipole moment**: If the dipole moment jumps or changes sign abruptly, the electron distribution has rearranged in a non‑trivial way.  
- **Orbital nature**: Visualise the frontier orbitals (`.mos` file or via `molden` from `xtb`) at each scan step. If the HOMO and LUMO swap their localisation (e.g., from one heterocycle to the other) without a smooth transition, it suggests a crossing of orbital configurations that might require multi‑state averaging.  
- **sTDA‑xTB state characters**: The output (`tda.out`) shows the dominant excitations (e.g., HOMO→LUMO, HOMO−1→LUMO). If the leading configuration changes abruptly along the path, the adiabatic state is switching character, which can hint at a true crossing or a strongly avoided crossing.

### 3.5. Triplet instability of the closed‑shell singlet
- Compute the singlet–triplet gap at each geometry (with `xtb --gfn2 --tda --triplet`). If the triplet state drops below the singlet ground state, you have a singlet–triplet crossing, a clear sign that a multireference description (at least two‑configuration) is mandatory.

## 4. How robust is the topology from cheap methods?

**Strengths:**
- The overall shape (well‑defined minima, broad barriers, the presence/absence of a second minimum) is usually correct.
- The **number and rough location** of avoided crossings between excited states often persists, because it originates from the symmetry and orbital energy ordering, which semiempirical methods capture reasonably well.

**Weaknesses:**
- Quantitative energies are off (ΔE can be wrong by 5–15 kcal/mol).
- sTDA‑xTB and TD‑DFTB can **miss** real conical intersections involving the ground state (they are not state‑averaged) and may artificially smooth out intersections. They can also produce **false intersections** if the single‑reference approximation breaks down.
- Spin contamination in UHF‑xTB may exaggerate multireference character or, conversely, suppress it if the solution remains artificially spin‑pure.

Nevertheless, as a **diagnostic** tool: if you see **well‑separated states everywhere** (>1 eV gap) and no sudden character changes, you can confidently stay with single‑reference methods. If the cheap scan raises red flags (narrow gaps, spin contamination >1.0, state crossings), then follow up those specific molecules with a higher‑level check (e.g., DFT with T1 diagnostic, or a small CASSCF).

## 5. Step‑by‑step protocol to assess “simple vs. complicated”

1. **Run a ground‑state neutral scan** with xTB. Note the HOMO–LUMO gap along the path. If it stays above ~2 eV and no singlet–triplet instability appears, the ground state is single‑reference.
2. **Charge the system** (-1 or +1) and rerun the scan with UHF‑xTB.  
   - Check `<S**2>` at each point.  
   - Watch for sudden jumps in spin density localisation.  
   - If both are smooth, the charged‑state PES is single‑reference.
3. **For excited states**, compute the first 3–5 singlet excitation energies with `sTDA‑xTB` at selected geometries along the path (especially near the TS, the FC point, and the product).  
   - Plot the adiabatic PES of the state you would populate (e.g., the one with largest oscillator strength or a specific excitation character).  
   - Check whether this state comes within <0.3 eV of another state of the same symmetry. If yes, a multi‑state treatment may be needed.  
   - Check if the leading excitation character changes sharply.
4. **If any of the above flags appear:**  
   - Run a **DFT single‑point** (e.g., B3LYP/def2‑SVP) at a few key geometries and check the T1 diagnostic (in ORCA, `! T1`). If T1 > 0.02, multireference is advised.  
   - Alternatively, perform a **CASSCF(2,2)** (2 electrons in 2 active orbitals) exploration at those geometries to see if the cheap method’s topology was trustworthy.
5. **If no flags appear:** You are safely in a regime where TDDFT or simple DFT for charged states is accurate, and the yields can be ranked using the descriptors (slope, barrier, Huang–Rhys) as discussed earlier.

## 6. Tools to automate the analysis

- Write a Python script that reads `xtbscan.log` or `tda.out` and extracts energies, gaps, `<S**2>`.  
- Plot energies vs. coordinate, colouring the states by their leading excitation (or spin density).  
- You can use `matplotlib` to visualise the PES landscape and quickly spot crossings or degeneracies.

## Final advice

Yes, cheap methods are perfectly suited to **pre‑screen the PES topology** and decide if you are in the “simple” regime. The key is to **look for degeneracies, sudden character changes, and large spin contamination**—these are robust warning signs that survive the semiempirical noise. When absent, you can trust the single‑reference picture for ranking; when present, invest in a more expensive validation only for those problematic candidates. This workflow will save enormous computational effort in your high‑throughput campaign.

---

# Kimi 2.6 chat

You're absolutely right that topological features are often robust across methods, and this is a smart screening strategy. Let me walk you through exactly how to do this and what to look for.

## How to Do the Cheap PES Scans

### Step 1: Define Your Reaction Coordinate

For proton transfer between heterocycles, use:
- **Primary coordinate**: d(N-H) or d(O-H) distance (the transferring proton)
- **Secondary constraints**: Keep d(N···N) or d(N···O) approximately fixed, or let it relax — depends on whether you want the "intrinsic" PT barrier or the full relaxed barrier

For heterocyclic pairs, the PT coordinate is usually well-defined. For concerted PCET, you may need two coordinates (proton + electron).

### Step 2: Ground State Scan (GFN2-xTB or DFTB3)

```bash
# Example with xtb
xtb --input scan.inp geom.xyz --opt
```

**scan.inp:**
```
$constrain
  distance: 3, 1, 1.0  # atom indices for N(proton donor) and H
$scan
  1.0, 2.0, 20         # from 1.0 to 2.0 Å, 20 steps
$end
```

This gives you E_ground(R_NH).

### Step 3: Charged State Scans

**For n+1 (anion, electron injection):**
- GFN2-xTB: run with `--chrg -1` (or appropriate charge)
- DFTB+: set charge in input, use SCC with extra electron

**For n-1 (cation, hole injection):**
- Same with `--chrg +1`

**Important:** You need the **relaxed** PES for the charged state. That means:
- Optimize geometry at each constrained R_NH
- Or at minimum do a single-point on the ground-state geometry (vertical), then relaxed scan

### Step 4: Excited State Scan

**sTDA-xTB** (available in xtb ≥ 6.4):
```bash
xtb geom.xyz --sTDA --chrg 0 --opt
```
This gives you S₁, S₂, etc. energies.

**For DFTB:** TD-DFTB exists but parameter coverage for heterocycles is limited. Prefer sTDA-xTB for excited states.

### Step 5: Plot and Overlay

Plot on same axes:
- E_ground(R)
- E_n+1(R) or E_n-1(R)  
- E_S1(R) (from sTDA-xTB)

Shift energies so reactant minimum of ground state = 0 for reference.

## What Exactly to Look For

### 1. Ground State Regime Classification

| Feature | Interpretation | Risk Level |
|---------|---------------|------------|
| Single well, no barrier | Spontaneous PT, too reactive for your "sweet spot" | Low risk (just exclude) |
| Double well, barrier > 15 kcal/mol | Kinetically stable, needs strong activation | Low risk |
| Double well, barrier 5-15 kcal/mol | **Sweet spot candidate** | Medium risk — check excited state |
| Very flat PES near TS | Strong anharmonicity, tunneling important | Medium risk |

### 2. Charged State Topology — Critical Diagnostics

Look at how E_n±1(R) compares to E_ground(R):

**Case A: Charged state crosses ground state before the TS**
```
Energy
  │    / E_n+1
  │   /  ×←── crossing
  │  /  /│
  │ /  / │    ← barrier on ground state
  │/  /  │
  └──/───┼──────→ R
    react  TS
```
- **Interpretation:** Electron injection creates a conical intersection or avoided crossing near the TS
- **Implication:** Very efficient PCET — electron transfer drives proton transfer
- **Risk:** If crossing is very early, you may have stepwise ET-PT rather than concerted PCET. Check if the crossing geometry has the proton still on donor (ET first) or already transferred (concerted).

**Case B: Charged state is downhill throughout, no crossing**
- **Interpretation:** Electron injection makes PT thermodynamically favorable everywhere
- **Implication:** Barrierless or nearly barrierless PT in charged state
- **Risk:** May be too exothermic — check Marcus inverted region effects (but for screening, this is likely a "good" candidate)

**Case C: Charged state crosses but far from TS, or stays above ground state**
```
Energy
  │         / E_n+1
  │        /
  │    ×──/     ← crossing far from TS
  │   /│ /
  │  / │/    ← ground state TS
  │ /  ×
  └──/──────→ R
```
- **Interpretation:** Charged state doesn't help much with PT
- **Implication:** Electron injection doesn't efficiently catalyze PT
- **Risk:** You need optical excitation or different mechanism

### 3. Excited State Topology

**Look for:**

| Feature | Good/Bad for Yield | What It Means |
|---------|-------------------|---------------|
| S₁ has minimum at product geometry | **Good** | Optical excitation directly prepares PT product |
| S₁ crosses S₀ near TS or product | **Good** | Efficient funnel to ground state product |
| S₁ is repulsive along PT coordinate from reactant | **Interesting** | "Impulse" mechanism — excitation launches wavepacket toward product |
| S₁ and S₀ are parallel (no crossing, S₁ always above) | **Bad** | No efficient decay channel, long-lived excited state, low yield |
| S₁/S₀ conical intersection near reactant | **Bad** | Fast internal conversion back to reactant before PT |

### 4. The "Sweet Spot" Signature You're Looking For

```
Energy
  │              / S₁ (or E_n+1)
  │             /
  │            /  ×←── CI with S₀ near product
  │           /  /│
  │    ──────/──/─┼────  ← S₀ product ≈ S₀ reactant (thermoneutral)
  │          /  / │
  │    ×────/──/  │      ← S₀ TS barrier ~10 kcal/mol
  │   /│   /  /   │
  │  / │  /  /    │
  └──/──┴─/──/────┴────→ R
    R    TS   P
    react    product
```

**Key features:**
- Ground state: barrier exists (doesn't happen spontaneously), product ≈ reactant energy or slightly uphill
- Excited/charged state: crosses ground state near or after TS, or has strong downhill slope
- CI or avoided crossing exists where system can funnel to product

## Specific Red Flags That Demand Higher-Level Methods

### 1. Near-Degeneracy at Critical Points

**What to look for:** At the TS or crossing point, check the xTB/DFTB orbital energies or natural orbital occupations.

In xTB output, look at:
- Wiberg bond orders: Does N-H bond order go to ~0.5 at TS? (Expected for PT)
- Charges: Does the transferring proton have partial positive charge throughout? (Expected)

**Red flag:** If you see:
- Multiple orbitals within 0.5 eV at the TS
- HOMO-LUMO gap collapses to <1 eV at any point along the coordinate
- Natural orbital occupations deviate significantly from 0 or 2 (e.g., 1.2, 0.8)

**Action:** This suggests multireference character. Run a quick CASSCF(2,2) or check with broken-symmetry DFT.

### 2. Spin Contamination in Charged States

For UHF/UDFT (which xTB uses for open-shell):
- Check ⟨S²⟩ in the xTB output (if available) or run a quick UKS calculation
- **Red flag:** ⟨S²⟩ > 0.9 for doublets (expected ~0.75), or > 2.1 for triplets (expected ~2.0)
- **Action:** Indicates spin contamination, possible biradical character. Use ROHF/RKS or CASSCF.

### 3. Charge Separation Artifacts

**What to look for:** In the charged state scan, does the extra electron/hole localize correctly?

**Red flag:** 
- In anion state, electron localizes on wrong moiety (not the acceptor)
- In cation state, hole delocalizes over entire molecule instead of donor
- This is common in TDDFT and can affect xTB too

**Test:** Compare Mulliken/Löwdin charges (from DFTB or quick DFT) at reactant and product. The charge should "follow" the proton in PCET, or be on the correct fragment for stepwise mechanisms.

### 4. Conical Intersection Topology

Cheap methods can find CIs, but the **dimensionality** matters:

- **Seams vs. points:** A true CI is a seam (N-2 dimensional). Cheap methods often find approximate points.
- **Look for:** Does the CI persist when you vary a second coordinate (e.g., N···N distance)? If it disappears, it may be an artifact.

**Red flag:** CI found with xTB but disappears at DFT level → likely artifact of parametrization.

### 5. Barrier Height Discrepancy

**Calibration check:** Run 3-5 representative systems at DFT (B3LYP-D3/def2-SVP) and compare barriers to xTB.

| xTB barrier vs. DFT | Interpretation |
|---------------------|---------------|
| Within 2-3 kcal/mol | xTB is reliable for trends |
| Systematically low by 5+ kcal/mol | xTB over-stabilizes TS (common with GFN2) |
| Systematically high | Less common, but check |
| Non-systematic errors | Different mechanisms have different errors — dangerous for trends |

## Practical Workflow

```
For each molecular pair:
  │
  ▼
┌─────────────────────────┐
│ 1. GFN2-xTB ground state│
│    optimize reactant,   │
│    product, TS guess    │
└─────────────────────────┘
  │
  ▼
┌─────────────────────────┐
│ 2. Constrained scan:    │
│    E_ground(R_NH)       │
│    E_n+1(R_NH)          │
│    E_n-1(R_NH)          │
│    E_S1(R_NH) [sTDA]    │
└─────────────────────────┘
  │
  ▼
┌─────────────────────────┐
│ 3. Plot and classify:   │
│    - Ground state regime│
│    - Charged state type │
│    - Excited state slope│
│    - Crossing positions │
└─────────────────────────┘
  │
  ▼
┌─────────────────────────┐
│ 4. Red flag check:      │
│    - HOMO-LUMO gap?     │
│    - Orbital degeneracy?│
│    - Charge localization?│
│    - Spin contamination?│
└─────────────────────────┘
  │
  ├── No red flags ──► Keep for Tier 2 (CDFT/DFT validation)
  │
  └── Red flags ─────► Flag for CASSCF/NEVPT2 spot-check
```

## What You Can Conclude from Cheap Scans

| Observation | Conclusion | Next Step |
|-------------|-----------|-----------|
| Clean double wells, clear crossings, no orbital degeneracy | Simple regime | CDFT-DFT for quantitative barriers and coupling |
| Flat PES, near-degenerate orbitals at TS, ambiguous charge localization | Multireference likely | CASSCF(2,2) or (4,4) minimum active space |
| CT state in S₁ with large oscillator strength | TDDFT may fail | Check with ADC(2) or sTDA-xTB vs. TDDFT |
| Multiple close-lying excited states | Strong non-adiabatic coupling | Need NACME or surface hopping |
| S₁/S₀ crossing near reactant | Fast internal conversion | Likely low yield unless barrier is very low |

## One Important Caveat

**xTB and DFTB struggle with:**
- **Proton-shared symmetric TS** (e.g., [N···H···N]⁺): The symmetric delocalization is often poorly described
- **Strong charge transfer states:** xTB may not capture the correct asymptotic behavior
- **Excited states with double excitation character:** sTDA-xTB is TDA-based, misses some correlation effects

**Test:** For 2-3 systems, compare xTB TS geometry to DFT. If the proton position differs by >0.1 Å, the PES topology may be qualitatively wrong.

## Summary

Your instinct is correct: cheap PES scans are excellent for **regime classification**. Look for:
1. **Ground state:** Barrier exists but is moderate (5-15 kcal/mol)
2. **Charged state:** Crosses ground state near TS or product, or is strongly downhill
3. **Excited state:** Has negative slope from reactant or CI near product
4. **No red flags:** No orbital degeneracy, no spin contamination, charge localizes correctly

If these conditions are met, you can confidently move to CDFT-DFT for quantitative barriers and coupling. If not, flag for multireference treatment.

Would you like me to elaborate on how to set up the constrained scans in specific codes (xtb, DFTB+, ORCA), or how to automate the red-flag detection?

---

# Mistral

Here’s **exactly how to use cheap methods (DFTB, GFN2-xTB) to scan PES for charged/excited states**, check topological features (crossings, conical intersections), and decide if you need higher-level theory.

### **✅ Yes, You Can Use Cheap Methods for Topology**
**Robust features** (usually correct even with DFTB/xTB):
- **Minima/maxima locations** (barriers, wells)
- **Avoided crossings** (close approaches without touching)
- **Conical intersections** (if they exist, cheap methods often find *a* crossing, even if not exact)
- **Barrierless vs. activated pathways**

**Fragile features** (may be wrong):
- **Exact crossing energies** (quantitatively off by 0.5–1.5 eV)
- **Charge-transfer state topology** (DFTB/TD-DFTB struggles)
- **Spin-state ordering** (if open-shell)

**➡️ Bottom line**: For **organic heterocycles**, cheap methods are **excellent for qualitative PES topology**. Use them to **triage** which systems need CASSCF/TDDFT.

### **🔧 Step-by-Step: How to Scan PES with Cheap Methods**

#### **1️⃣ Ground-State PES (Baseline)**
**Method**: **GFN2-xTB** (faster) or **DFTB3** (more accurate for barriers)
**Tool**: `xtb` (for GFN2-xTB) or `dftb+` (for DFTB3)
**Steps**:
```bash
# Example with xtb (GFN2-xTB)
xtb input.xyz --opt --constrain "distance,1,2,1.0"  # Fix H donor-acceptor distance to 1.0 Å
xtb input.xyz --opt --constrain "distance,1,2,1.1"
# ... repeat for 10–20 points along your RC (e.g., proton transfer coordinate)
```
**What to plot**: Energy vs. RC (e.g., `d(O-H) - d(H-N)`).
**Look for**:
- Clear minima (reactant/product)
- Transition state (maximum)
- Barrier height (ΔE‡)

#### **2️⃣ Charged-State PES (n+1 or n-1)**
**Method**: Same as above, but **add/remove an electron**.
**Steps**:
```bash
# For cation (n-1):
xtb input.xyz --opt --charge 1 --constrain "distance,1,2,1.0"
# For anion (n+1):
xtb input.xyz --opt --charge -1 --constrain "distance,1,2,1.0"
```
**Key question**: *Does the barrier disappear or invert?*
- **If ΔE‡_charged ≈ 0 or negative**: Electron/hole injection **triggers spontaneous PT** (good for your sweet spot).
- **If ΔE‡_charged > ΔE‡_ground**: Injection **doesn’t help** (bad).

**⚠️ Check charge localization**:
- Use `xtb --pop` or `dftb+ --mulliken` to confirm the extra electron/hole stays on the acceptor (not delocalized).

#### **3️⃣ Excited-State PES (S₁, S₂, etc.)**
**Option A: TD-DFTB (Best for PES Scans)**
- **Tool**: `dftb+` with TD-DFTB or **LC-TD-DFTB** (long-range corrected, better for CT states).
- **Steps**:
  ```bash
  # First, get ground-state geometries at each RC point (as above)
  # Then, for each geometry, compute excited states:
  dftb+ input.gen -D "TD { }"  # Standard TD-DFTB (PBE-based)
  dftb+ input.gen -D "TD { LC = Yes }"  # LC-TD-DFTB (better for CT)
  ```
- **Output**: Excited-state energies (E_S₁, E_S₂, ...) at each RC point.
- **Plot**: E_S₁ vs. RC on the same graph as ground state.

**Option B: sTDA-xTB (New, Fast)**
- **What it is**: Simplified TDA (Tamm-Dancoff Approximation) for xTB.
- **Where**: [sTDA-xTB paper](https://doi.org/10.1021/acs.jctc.2c00406) (2022) + [GitHub](https://github.com/grimme-lab/xtb).
- **Steps**:
  ```bash
  xtb input.xyz --sTDA  # Computes S₁ energy at ground-state geometry
  ```
- **Limitation**: No gradients yet (single-point only), but you can **interpolate** PES.

**Option C: ZINDO/S (Fastest, Least Accurate)**
- **Tool**: Gaussian, ORCA, or standalone ZINDO.
- **Use case**: Quick check for **excitation energies only** (not PES gradients).
- **Steps**:
  ```bash
  # In Gaussian:
  %chk=file.chk
  # ZINDO SCF
  file.com
  ```

### **🎯 What to Look For in Your PES Plots**
#### **🔍 1. Crossings vs. Avoided Crossings**
| Feature | What It Looks Like | What It Means | Action |
|---------|--------------------|---------------|--------|
| **Avoided crossing** | Two PES approach closely but **don’t touch** (gap > 0.1 eV) | Non-adiabatic coupling is **weak** | Simple regime; DFT/TDDFT is fine |
| **Conical intersection** | Two PES **touch at a point** (gap ≈ 0) | Non-adiabatic coupling is **strong** | May need **CASSCF** for dynamics |
| **Seam of crossing** | PES touch along a **line** (2D RC) | Degenerate states | **CASSCF/MRCI** required |

**Example**:
```
Energy
  ^
  |       / S₁
  |      /
  |_____/______ S₀ (ground)
  |    *
  |----+----+----> RC
       |    |
     Avoided  Conical
     Crossing Intersection
```

#### **🔍 2. Barrier Topology Changes**
| Ground State | Charged/Excited State | Interpretation |
|--------------|----------------------|----------------|
| Barrier (ΔE‡ > 0) | Barrier disappears (ΔE‡ ≈ 0) | **Sweet spot**: Injection/excitation triggers PT |
| Barrier (ΔE‡ > 0) | Barrier higher (ΔE‡_excited > ΔE‡_ground) | **Bad**: Injection doesn’t help |
| Barrierless | Barrierless | **Spontaneous PT**: Avoid (not controllable) |

#### **🔍 3. Minimum Energy Crossing Point (MECP)**
- **What it is**: The point where ground and excited/charged PES are **closest**.
- **Why it matters**: If the MECP is **low in energy**, non-adiabatic transitions are likely.
- **How to find it**:
  - Plot **ΔE = E_excited - E_ground** vs. RC.
  - Look for the **minimum ΔE** (not necessarily zero!).

**Example**:
```
ΔE (eV)
  ^
1.0|       *
   |      / \
   |     /   \
0.5|    *     *
   |   /       \
0.0|__*_________*__> RC
     MECP
```

- **If ΔE_MECP < 0.5 eV**: Strong coupling → **non-adiabatic regime** (may need TDDFT/CASSCF).
- **If ΔE_MECP > 1.0 eV**: Weak coupling → **adiabatic regime** (DFT is fine).

#### **🔍 4. Slope Comparison (Driving Force)**
- **What to plot**: `dE/dRC` (force) for ground vs. excited/charged state at **RC = reactant geometry**.
- **What it means**:
  - **Steeper slope in excited state** → Stronger driving force for PT.
  - **Flat slope** → Weak coupling to RC (PT unlikely).

**Example**:
```
Force
  ^
  |     / S₁ (steep)
  |    /
  |___/______ S₀ (shallow)
  |----------> RC
```

### **🚨 Red Flags: When to Use CASSCF/TDDFT**
| **Cheap Method Shows...** | **Likely Reality** | **Action** |
|----------------------------|-------------------|------------|
| **Flat PES with no clear minima** | Strong correlation (diradical, TM) | **CASSCF** |
| **Multiple close-lying states (<0.2 eV gap)** | Near-degeneracy | **CASSCF/MRCI** |
| **Conical intersection** | Non-adiabatic dynamics | **CASSCF + dynamics** |
| **Charge-transfer state dominates** | TDDFT/GGA fails | **Range-separated TDDFT (CAM-B3LYP, ωB97X-D)** |
| **Transition metals (Fe, Cu, Ni)** | Multireference character | **CASSCF/NEVPT2** |
| **PES topology changes wildly with method** | Method-dependent artifacts | **Validate with DFT/TDDFT** |

**✅ Green Flags: Simple Regime (DFTB/xTB is Enough)**
- Clear single barrier in ground state.
- Charged/excited state PES is smooth and well-behaved.
- No crossings or avoided crossings near RC of interest.
- ΔE_MECP > 0.5 eV (weak non-adiabatic coupling).

### **📊 Practical Workflow for Your Case**
#### **Phase 1: Fast Triage (1000s of Molecules)**
1. **Ground-state PES**: GFN2-xTB constrained scan (10 points).
2. **Charged-state PES**: GFN2-xTB with ±1 charge (same RC points).
3. **Plot**: E_ground, E_cation, E_anion vs. RC.
4. **Filter**:
   - Keep only systems where **E_ground has a barrier** (ΔE‡ > 0).
   - Keep only systems where **E_cation or E_anion has ΔE‡ ≈ 0 or < 0.2 eV**.

#### **Phase 2: Excited-State Check (100s of Molecules)**
1. **TD-DFTB or LC-TD-DFTB**: Compute S₁ energy at **3–5 key RC points** (reactant, TS, product).
2. **Plot**: E_S₁ vs. RC (interpolate if needed).
3. **Filter**:
   - Keep systems where **E_S₁ < E_ground** at some RC (photoinduced PT possible).
   - Check for **crossings/avoided crossings** with ground state.

#### **Phase 3: Validate Top Candidates (10–20 Molecules)**
1. **DFT (ωB97X-D3/def2-SVP)**: Recompute PES for ground/charged states.
2. **TDDFT (CAM-B3LYP/def2-SVP)**: Recompute S₁ PES.
3. **Check**:
   - Does topology match cheap methods?
   - Are crossings real or artifacts?

#### **Phase 4: Final Check for Complicated Cases**
- If any system shows **conical intersections, flat PES, or near-degeneracy**:
  - Run **CASSCF(2,2)/6-31G*** at a few points to confirm.

### **💡 Pro Tips**
1. **Use a collective RC**: For heterocycles, try:
   ```
   RC = d(H-donor) - d(H-acceptor) + α*(d(donor-acceptor))
   ```
   (α = 0.1–0.2 to include heavy-atom motion).

2. **Start with GFN2-xTB**:
   - Faster than DFTB, often more accurate for organic barriers.
   - Use `--gfn2` flag in `xtb`.

3. **For excited states, prioritize LC-TD-DFTB**:
   - Standard TD-DFTB (PBE-based) **fails for charge-transfer states** (common in PCET).
   - LC-TD-DFTB is **10x slower** but worth it.

4. **Automate with Python**:
   ```python
   import subprocess
   import numpy as np
   import matplotlib.pyplot as plt

   rc_points = np.linspace(0.8, 2.0, 20)  # H-donor distance in Å
   energies = []
   for r in rc_points:
       # Write constrained input
       with open("input.xyz", "w") as f:
           f.write(f"3\n\nO 0 0 0\nH 0 0 {r}\nN 0 0 3\n")
       # Run xtb
       subprocess.run(f"xtb input.xyz --opt --constrain 'distance,2,3,{r}' --charge 0", shell=True)
       # Parse energy from xtb output
       energy = parse_energy("xtb.log")
       energies.append(energy)
   plt.plot(rc_points, energies)
   ```

5. **Visualize in 2D**:
   - If you have **two RCs** (e.g., proton transfer + heavy-atom motion), plot a **2D PES heatmap**.
   - Conical intersections appear as **X-shaped features**.

### **📌 Summary: Your Decision Tree**
```
1. Run GFN2-xTB constrained PES for ground state → Barrier?
   ├── NO (barrierless) → Discard (spontaneous PT)
   └── YES → Go to 2

2. Run GFN2-xTB PES for n+1/n-1 → Barrier gone?
   ├── NO → Discard (injection doesn’t help)
   └── YES → Go to 3

3. Run LC-TD-DFTB for S₁ at 3–5 RC points → Crossing with ground state?
   ├── NO crossing, ΔE_MECP > 0.5 eV → Simple regime (DFT/TDDFT is fine)
   ├── Crossing or ΔE_MECP < 0.3 eV → Non-adiabatic regime (may need CASSCF)
   └── Flat PES or multiple close states → Strong correlation (CASSCF/MRCI)
```

### **🔗 Key References**
- **GFN2-xTB for PES**: [JCTC 2019, 15, 3080](https://doi.org/10.1021/acs.jctc.8b01176) (barrier benchmarks)
- **LC-TD-DFTB**: [PCCP 2020, 22, 2008](https://doi.org/10.1039/C9CP05753F) (charge-transfer states)
- **sTDA-xTB**: [JCTC 2022, 18, 5174](https://doi.org/10.1021/acs.jctc.2c00406) (excited states for xTB)
- **PCET topology**: [Chem. Rev. 2014, 114, 4675](https://doi.org/10.1021/cr400484g) (Hammes-Schiffer)

---

# USER

look in @PCET_methods.chat.md 

can you make metanalysis, what are good ideas, what s inovative and intersting, where the LLMs agree, where disagree, which questions from propesed desing needs to clarify and make design decission, how would you suggest it based on the review, your experience, judgement, creatvity and expertiese

---

# Kimi 2.7

# Meta-Analysis of [PCET_methods.chat.md](cci:7://file:///home/prokophapala/git/CompChemUtils/doc/PCET_methods.chat.md:0:0-0:0)

## Good Ideas (Consensus Winners)

The LLMs converge on a few robust, practical ideas:

- **Tiered workflow for high-throughput screening**: cheap semiempirical scan → DFT validation → high-level methods only for problematic cases. This is the backbone of every answer.
- **GFN2-xTB / g-xTB as a fast topology generator**, with **ωB97X-D / M06-2X / CAM-B3LYP** as the validation/recalibration layer.
- **CASSCF is not a screening tool** for ordinary heterocyclic PCET; reserve it for red-flag cases (diradicals, conical intersections, severe spin contamination).
- **Constrained PES scans are preferable to MD** for the stated goal: define a reaction coordinate, relax all other DOFs, and sample energy/forces/slopes.
- **Reaction coordinate**: `q = r(D-H) - r(A-H)` is the cleanest 1D descriptor for proton transfer.
- **“Sweet spot” ranking**: stable in ground state (finite barrier), but low barrier or steep downhill slope in the triggered state.
- **Red flags for multireference**: spin contamination, HOMO-LUMO gap collapse, root swapping, broken-symmetry solutions, abrupt charge jumps.

## Innovative & Interesting Highlights

| Idea | Source | Why it stands out |
|------|--------|-------------------|
| **Minimal yield proxy**: `B₀, B*, F*(q_FC), Δq, S_q` | ChatGPT 5.5 | Reduces the entire problem to a few cheap, physically interpretable descriptors. |
| **Constrained DFTB (C-DFTB) for charge localization** | Gemini | A genuinely scalable way to enforce localized electron/hole injection in DFTB+ without paying DFT cost. |
| **ΔSCF for excited-state PES scans** | Grok | Often overlooked; ΔSCF can give relaxed CT-state geometries where linear-response TDDFT struggles. |
| **Decision tree with Marcus / Landau-Zener rates** | Kimi 2.6 | Moves beyond barrier ranking toward a rate-based yield estimate using `H₁₂`, `λ`, `ΔG`. |
| **MECP (Minimum Energy Crossing Point) as a screening metric** | Mistral | `ΔE_MECP < 0.5 eV` vs. `> 1.0 eV` gives a clean triage criterion for nonadiabaticity. |
| **“Simple vs. complicated” protocol with explicit thresholds** | DeepSeek-V4-pro | Most concrete: check `<S²>`, gap < 1 eV, state gaps < 0.3 eV, T1 diagnostic > 0.02. |
| **Huang-Rhys factor of the proton-stretch mode as a descriptor** | Gemini | Focuses on the `N-H/O-H` stretch (~3000 cm⁻¹) as the vibronic fingerprint of PT activity. |

## Where LLMs Agree

- **Ground-state electron/hole injection does not require TDDFT** — just the correct charged-state PES.
- **Optical excitation requires an excited-state method** — at minimum sTDA-xTB / TD-DFTB for screening, TDDFT for validation.
- **Heterocyclic organic PCET is mostly single-reference** — CASSCF is overkill unless diagnostics fail.
- **Range-separated hybrids are essential** for barriers and CT states; pure GGA functionals are unreliable.
- **Cheap methods are topology microscopes, not quantitative calculators** — use them for regime classification, then recalibrate with DFT.
- **No molecular dynamics is needed** for the stated goal of relative trends/yields.
- **Solvent/environment matters** and should be included at least via implicit solvation in validation.

## Where LLMs Disagree (Design Tensions)

### 1. Constrained DFT vs. adiabatic charged-state scans
- **Gemini, Kimi, Mistral**: C-DFT / C-DFTB is recommended or even “exactly what you want” to enforce charge localization.
- **ChatGPT, DeepSeek**: For initial screening, adiabatic PES scans (neutral/anion/cation at the same geometry) are sufficient. CDFT is a complication unless charge localization is genuinely problematic.

### 2. Best excited-state screening method
- **Gemini**: TD-DFTB (analytical gradients, ESIPT pathways).
- **ChatGPT 5.5**: sTDA-xTB first, then TD-DFTB.
- **Mistral**: LC-TD-DFTB is preferred over sTDA-xTB because TD-DFTB has PES gradients; sTDA-xTB is single-point only.
- **Kimi 2.6**: sTDA-xTB for initial screening, then TD-DFT.

### 3. Error estimates for cheap barriers
- **Mistral**: ±2–3 kcal/mol.
- **Gemini**: underestimates, can turn barriers into barrierless.
- **DeepSeek**: 5–10 kcal/mol off.
- **ChatGPT**: 10–20 kJ/mol.
These numbers are inconsistent, which is a warning not to trust any single quoted error bar.

### 4. Path-sampling method
- **Gemini, ChatGPT**: NEB / string.
- **Kimi**: metadynamics.
- **Mistral, DeepSeek**: constrained 1D scans.
For the stated goal, constrained scans are the cheapest and most controllable.

### 5. Rate-theory formalism
- **Kimi**: Marcus + Landau-Zener with CDFT `H₁₂`.
- **Mistral**: simplified Marcus yield proxy.
- **ChatGPT**: pure slope/barrier/displacement ranking.
- **Gemini**: Franck-Condon / Herzberg-Teller / Huang-Rhys.

### 6. Red-flag thresholds
- **Mistral**: MECP < 0.5 eV → nonadiabatic.
- **DeepSeek**: state gap < 0.3 eV → multistate; HOMO-LUMO < 1 eV → static correlation.
- **Kimi**: `<S²> > 0.9` for doublets.
These are heuristic and not universally agreed.

## Open Questions Requiring Your Decision

1. **What is the exact output?** A ranked list of pairs, a yield proxy, or absolute rate estimates?
2. **Which triggers are in scope?** Electron injection, hole injection, optical excitation, electric field — one workflow per trigger or a unified descriptor?
3. **Do you need CDFT?** Only if charge delocalization breaks the adiabatic cation/anion picture.
4. **What is the reaction coordinate for concerted PCET?** One coordinate (proton) or two (proton + charge transfer)?
5. **Solvent model** for the screening tier: ALPB (xTB), CPCM/SMD (DFT), explicit water, vacuum?
6. **Validation level**: ωB97X-D3/def2-SVP, def2-TZVP, or r2SCAN-3c?
7. **Excited-state method**: sTDA-xTB, TD-DFTB, LC-TD-DFTB, or TDDFT from the start?
8. **How to handle tunneling/ZPE**? Ignore for trends, or include Wigner/Eckart?
9. **Score function**: Which combination of `B₀`, `B*`, `F*`, `S`, `λ` gives the best ranking?
10. **Automation target**: Which tools in your existing stack (`py/interfaces/dftbplus.py`, ASE, xtb, ORCA) will drive the workflow?
11. **What to do when cheap methods find a CI**: validate, discard, or flag for CASSCF?
12. **How many pairs** and how many validation points per tier?

## My Recommendations

Based on your stated goal — **relative trends in photo/electron-induced PT yield across many heterocyclic pairs** — and your existing codebase (`CompChemUtils`) and scientific discipline (`AGENTS.md` rules), here is what I would build:

### 1. Adopt a 3-Tier Screening Architecture

| Tier | Method | Purpose | Fraction of pairs |
|------|--------|---------|-------------------|
| **T1** | GFN2-xTB/g-xTB constrained 1D scan | Topology, barrier, slope | 100% |
| **T2** | DFT (ωB97X-D3/def2-SVP) on selected points | Recalibrate barriers, validate charge localization | 10–20% |
| **T3** | TDDFT (CAM-B3LYP/ωB97X-D) or CDFT/CASSCF diagnostic | Only for optical candidates or red-flag cases | 1–5% |

**Why**: Start with the simplest adiabatic scans. Do **not** add CDFT unless Tier 1/Tier 2 shows that the cation/anion state is artificially delocalized.

### 2. Define a Single Clear Reaction Coordinate

For pure proton transfer:

```
q = r(D-H) - r(A-H)
```

For concerted PCET where the electron moves with the proton, add a second coordinate if needed:

```
q₁ = r(D-H) - r(A-H)
q₂ = charge on acceptor - charge on donor
```

But begin with one coordinate; only add `q₂` if the one-coordinate picture fails.

### 3. Compute a Minimal Descriptor Set

For each pair, compute:

- **Ground-state barrier**: `B₀ = E₀(q‡) - E₀(q_min)`
- **Triggered-state barrier**: `B* = E*(q‡) - E*(q_FC)`
- **Initial force**: `F* = -dE*/dq |_{q_FC}`
- **Relaxation energy**: `λ_q = E*(q_FC) - E*(q*_min)`
- **Huang-Rhys factor**: `S_q ≈ λ_q / (ℏω_q)`

Then rank by a score such as:

```
score = |F*| * exp(-B* / kT) / (B₀ + ε)
```

This favors: steep downhill slope, low triggered-state barrier, and a ground-state barrier large enough to prevent spontaneous transfer.

### 4. Use the Cheapest Excited-State Tool First

Use **sTDA-xTB** for the initial excited-state screening. It is fast, black-box, and available through `xtb`. If the state is strongly CT-character or shows root-swapping, **then** escalate to LC-TD-DFTB or TDDFT.

**Note**: The claim that TD-DFTB has analytical excited-state gradients in DFTB+ is correct, but in practice it is parameter-dependent and fragile for arbitrary heterocycles. sTDA-xTB is the safer broad-coverage screening tool.

### 5. Do Not Use CDFT by Default

Run adiabatic cation/anion scans first. Use Mulliken/ESP charges or spin density to check localization. If the charge does not sit where it should, then introduce CDFT or broken-symmetry DFT only for those specific pairs.

### 6. Automate, But Keep Python Minimal

Build a single-purpose tool in the repo, e.g., `py/tasks/pcet_screen.py`, that:

1. Reads a list of pairs.
2. Runs `xtb` constrained scans.
3. Parses energies, forces, and red flags.
4. Writes a JSON/CSV report with descriptors and scores.
5. Flags suspicious cases for DFT validation.

Do not over-abstract. The orchestration should be thin; the heavy work is done by `xtb` / DFTB+ / ORCA.

### 7. Add a Calibration Step First

Before screening hundreds of pairs, validate 5–10 representative systems against DFT. Compare:

- Barrier heights
- Proton position in the TS
- Charge/spin localization
- State ordering

If GFN2-xTB/g-xTB trends correlate with DFT (e.g., Spearman rank correlation > 0.8), proceed. If not, fix the screening method before scaling up.

### 8. Include Solvent in Validation, Not Screening

Run the screening tier in vacuum or with the xTB ALPB model. Add CPCM/SMD in the DFT validation tier. Solvent can flip acidity/basicity rankings and should not be ignored, but it is not the first variable to optimize.

### 9. Treat Red Flags as Stop Conditions, Not Suggestions

If a cheap scan shows:

- `<S²>` far from expected for the multiplicity
- HOMO-LUMO gap < 1 eV near the TS
- Multiple roots within 0.3–0.5 eV
- SCF instability or root swapping
- Charge localization on the wrong fragment

then flag the pair and **do not** include it in the screening ranking until validated. Do not silently average or ignore these.

### 10. Keep CASSCF as a Diagnostic, Not a Tier

For ordinary heterocycles, CASSCF is unlikely to be needed. If red flags persist after DFT validation, use a small active space (e.g., CAS(2,2) or CAS(4,4)) on the critical geometry only, not across the whole library.

## Summary of the Design Decision

- **Trigger**: model electron/hole injection with adiabatic charged-state scans; model optical with sTDA-xTB.
- **Coordinate**: 1D proton transfer coordinate first.
- **Screening**: GFN2-xTB/g-xTB.
- **Validation**: ωB97X-D3/def2-SVP; TDDFT for optical; CDFT only if charge localization fails.
- **Ranking**: score = slope × exp(-triggered barrier) / ground-state stability.
- **Multireference**: diagnostic only, triggered by explicit red flags.

This keeps the workflow computationally efficient, physically grounded, and aligned with the fail-loud, minimal-orchestration philosophy of your codebase.
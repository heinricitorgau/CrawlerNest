package clawer.service;

import clawer.dto.AdmissionDTO;
import clawer.model.AdmissionRequirement;
import clawer.repository.AdmissionRequirementRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class AdmissionService {

    private final AdmissionRequirementRepository admissionRequirementRepository;

    public AdmissionService(AdmissionRequirementRepository admissionRequirementRepository) {
        this.admissionRequirementRepository = admissionRequirementRepository;
    }

    public List<AdmissionDTO> getAllAdmissions() {
        return admissionRequirementRepository.findAll().stream()
                .map(this::toDTO)
                .collect(Collectors.toList());
    }

    private AdmissionDTO toDTO(AdmissionRequirement admissionRequirement) {
        AdmissionDTO dto = new AdmissionDTO();
        dto.setId(admissionRequirement.getId());
        dto.setGpaMin(admissionRequirement.getGpaMin());
        dto.setIeltsMin(admissionRequirement.getIeltsMin());
        dto.setToeflMin(admissionRequirement.getToeflMin());
        dto.setGreMin(admissionRequirement.getGreMin());
        dto.setGmatMin(admissionRequirement.getGmatMin());

        if (admissionRequirement.getUniversity() != null) {
            dto.setUniversityId(admissionRequirement.getUniversity().getId());
            dto.setUniversityName(admissionRequirement.getUniversity().getDisplayName());
        }

        return dto;
    }
}

package clawer.dto;

public class RankingCountryOptionDTO {
    private String code;
    private String name;
    private long count;

    public RankingCountryOptionDTO() {}

    public RankingCountryOptionDTO(String code, String name, long count) {
        this.code = code;
        this.name = name;
        this.count = count;
    }

    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public long getCount() { return count; }
    public void setCount(long count) { this.count = count; }
}
